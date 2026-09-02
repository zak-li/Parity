from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET

import pytest

from core.connectors.base import ConnectorError
from core.connectors.iso20022 import (
    Camt053Parser,
    CreditTransferInstruction,
    Pain001Generator,
)

SAMPLE_CAMT053_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt>
    <GrpHdr>
      <MsgId>MSG-2026-0001</MsgId>
      <CreDtTm>2026-03-15T08:30:00Z</CreDtTm>
    </GrpHdr>
    <Stmt>
      <Id>STMT-2026-001</Id>
      <CreDtTm>2026-03-15T08:30:00Z</CreDtTm>
      <Acct>
        <Id>
          <IBAN>FR7630006000011234567890189</IBAN>
        </Id>
        <Ccy>EUR</Ccy>
      </Acct>
      <Bal>
        <Tp>
          <CdOrPrtry>
            <Cd>OPBD</Cd>
          </CdOrPrtry>
        </Tp>
        <Amt Ccy="EUR">100000.00</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Dt>
          <Dt>2026-03-01</Dt>
        </Dt>
      </Bal>
      <Bal>
        <Tp>
          <CdOrPrtry>
            <Cd>CLBD</Cd>
          </CdOrPrtry>
        </Tp>
        <Amt Ccy="EUR">145000.00</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Dt>
          <Dt>2026-03-15</Dt>
        </Dt>
      </Bal>
      <Ntry>
        <NtryRef>TX-EXPORT-001</NtryRef>
        <Amt Ccy="USD">50000.00</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <BookgDt>
          <Dt>2026-03-10</Dt>
        </BookgDt>
        <ValDt>
          <Dt>2026-03-11</Dt>
        </ValDt>
        <NtryDtls>
          <TxDtls>
            <RltdPties>
              <Dbtr>
                <Nm>US Client Corp</Nm>
              </Dbtr>
            </RltdPties>
            <RmtInf>
              <Ustrd>Export invoice INV-2026-88</Ustrd>
            </RmtInf>
          </TxDtls>
        </NtryDtls>
      </Ntry>
      <Ntry>
        <NtryRef>TX-IMPORT-002</NtryRef>
        <Amt Ccy="EUR">5000.00</Amt>
        <CdtDbtInd>DBIT</CdtDbtInd>
        <BookgDt>
          <Dt>2026-03-12</Dt>
        </BookgDt>
        <ValDt>
          <Dt>2026-03-12</Dt>
        </ValDt>
        <NtryDtls>
          <TxDtls>
            <RltdPties>
              <Cdtr>
                <Nm>Logistics Partner SARL</Nm>
              </Cdtr>
            </RltdPties>
            <RmtInf>
              <Ustrd>Freight settlement invoice</Ustrd>
            </RmtInf>
          </TxDtls>
        </NtryDtls>
      </Ntry>
    </Stmt>
  </BkToCstmrStmt>
</Document>
"""


def test_camt053_parser_success():
    statement = Camt053Parser.parse(SAMPLE_CAMT053_XML)

    assert statement.statement_id == "STMT-2026-001"
    assert statement.iban == "FR7630006000011234567890189"
    assert statement.currency == "EUR"
    assert statement.opening_balance == pytest.approx(100000.00)
    assert statement.closing_balance == pytest.approx(145000.00)
    assert len(statement.entries) == 2

    # Verify conversions to Parity records
    sales = statement.to_sales_records()
    assert len(sales) == 1
    assert sales[0].id == "TX-EXPORT-001"
    assert sales[0].currency == "USD"
    assert sales[0].amount == pytest.approx(50000.00)

    purchases = statement.to_purchase_records()
    assert len(purchases) == 1
    assert purchases[0].id == "TX-IMPORT-002"
    assert purchases[0].currency == "EUR"
    assert purchases[0].amount == pytest.approx(5000.00)

    # Summary
    summary = statement.currency_summary()
    assert summary["USD"]["credits"] == pytest.approx(50000.00)
    assert summary["USD"]["net"] == pytest.approx(50000.00)
    assert summary["EUR"]["debits"] == pytest.approx(5000.00)
    assert summary["EUR"]["net"] == pytest.approx(-5000.00)


def test_camt053_parser_invalid_xml():
    with pytest.raises(ConnectorError):
        Camt053Parser.parse("this is not xml")

    with pytest.raises(ConnectorError):
        Camt053Parser.parse("<Document><OtherNode/></Document>")


def test_pain001_generator_success():
    transfers = [
        CreditTransferInstruction(
            end_to_end_id="E2E-HEDGE-01",
            amount=50000.00,
            currency="USD",
            creditor_name="Global FX Liquidity Ltd",
            creditor_iban="US33CHAS0000001234567890",
            creditor_bic="CHASUS33XXX",
            execution_date=dt.date(2026, 4, 1),
            remittance_info="Hedge settlement forward #492",
        ),
        CreditTransferInstruction(
            end_to_end_id="E2E-SUPP-02",
            amount=20000.00,
            currency="EUR",
            creditor_name="Component Supplier GmbH",
            creditor_iban="DE89370400440532013000",
            creditor_bic="DEUTDEDDFXX",
            execution_date=dt.date(2026, 4, 1),
            remittance_info="Raw materials advance payment",
        ),
    ]

    xml_str = Pain001Generator.generate(
        initiating_party="Acme Corp Treasury",
        debtor_name="Acme Corp SAS",
        debtor_iban="FR7630006000011234567890189",
        debtor_bic="BNPAFRPPXXX",
        transfers=transfers,
        message_id="MSG-TEST-001",
    )

    assert "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03" in xml_str

    # Parse to verify XML validity
    root = ET.fromstring(xml_str)
    # Strip namespaces
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]

    assert root.find(".//MsgId").text == "MSG-TEST-001"
    assert root.find(".//NbOfTxs").text == "2"
    assert root.find(".//CtrlSum").text == "70000.00"
    assert root.find(".//InitgPty/Nm").text == "Acme Corp Treasury"
    assert root.find(".//Dbtr/Nm").text == "Acme Corp SAS"
    assert root.find(".//DbtrAcct/Id/IBAN").text == "FR7630006000011234567890189"

    tx_nodes = root.findall(".//CdtTrfTxInf")
    assert len(tx_nodes) == 2
    assert tx_nodes[0].find(".//EndToEndId").text == "E2E-HEDGE-01"
    assert tx_nodes[0].find(".//InstdAmt").text == "50000.00"
    assert tx_nodes[0].find(".//InstdAmt").attrib["Ccy"] == "USD"


def test_pain001_generator_rejects_empty():
    with pytest.raises(ConnectorError):
        Pain001Generator.generate(
            initiating_party="Acme Corp",
            debtor_name="Acme Corp",
            debtor_iban="FR7630006000011234567890189",
            debtor_bic="BNPAFRPPXXX",
            transfers=[],
        )


def test_pain001_generator_rejects_negative_or_zero_amount():
    invalid_transfer = CreditTransferInstruction(
        end_to_end_id="TX-BAD",
        amount=-100.0,
        currency="EUR",
        creditor_name="Supplier",
        creditor_iban="DE89370400440532013000",
    )
    with pytest.raises(ConnectorError, match="non-positive amount"):
        Pain001Generator.generate(
            initiating_party="Acme Corp",
            debtor_name="Acme Corp",
            debtor_iban="FR7630006000011234567890189",
            debtor_bic=None,
            transfers=[invalid_transfer],
        )


def test_pain001_generator_rejects_invalid_iban():
    valid_transfer = CreditTransferInstruction(
        end_to_end_id="TX-1",
        amount=100.0,
        currency="EUR",
        creditor_name="Supplier",
        creditor_iban="DE89370400440532013000",
    )
    with pytest.raises(ConnectorError, match="Invalid debtor IBAN"):
        Pain001Generator.generate(
            initiating_party="Acme Corp",
            debtor_name="Acme Corp",
            debtor_iban="SHORT",
            debtor_bic=None,
            transfers=[valid_transfer],
        )


def test_camt053_parse_all_multiple_statements():
    multi_camt = """<?xml version="1.0" encoding="UTF-8"?>
    <Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
      <BkToCstmrStmt>
        <Stmt>
          <Id>STMT-EUR-01</Id>
          <Acct><Id><IBAN>FR7630006000011234567890189</IBAN></Id><Ccy>EUR</Ccy></Acct>
        </Stmt>
        <Stmt>
          <Id>STMT-USD-02</Id>
          <Acct><Id><IBAN>US33CHAS0000001234567890</IBAN></Id><Ccy>USD</Ccy></Acct>
        </Stmt>
      </BkToCstmrStmt>
    </Document>
    """
    stmts = Camt053Parser.parse_all(multi_camt)
    assert len(stmts) == 2
    assert stmts[0].statement_id == "STMT-EUR-01"
    assert stmts[0].currency == "EUR"
    assert stmts[1].statement_id == "STMT-USD-02"
    assert stmts[1].currency == "USD"


def test_camt053_rejects_xml_bomb():
    xml_bomb = (
        "<!DOCTYPE lolz ["
        '<!ENTITY lol "lol">'
        "<!ELEMENT lolz (#PCDATA)>"
        '<!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
        "]>"
        "<Document><lolz>&lol1;</lolz></Document>"
    )
    with pytest.raises(ConnectorError):
        Camt053Parser.parse(xml_bomb)
