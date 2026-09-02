from __future__ import annotations

import datetime as dt
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.dom import minidom

import defusedxml.ElementTree as defused_ET

from .base import ConnectorError, PurchaseRecord, SalesRecord


@dataclass(frozen=True, slots=True)
class CamtEntry:
    reference: str
    amount: float
    currency: str
    credit_debit: str  # "CRDT" or "DBIT"
    booking_date: dt.date
    value_date: dt.date | None = None
    counterparty_name: str | None = None
    remittance_info: str | None = None


@dataclass(frozen=True, slots=True)
class CamtStatement:
    statement_id: str
    iban: str
    currency: str
    creation_date: dt.datetime
    opening_balance: float | None
    closing_balance: float | None
    entries: tuple[CamtEntry, ...] = field(default_factory=tuple)

    def to_sales_records(self) -> list[SalesRecord]:
        """Convert incoming credit entries (CRDT) into SalesRecord instances."""
        return [
            SalesRecord(
                id=entry.reference,
                currency=entry.currency,
                amount=entry.amount,
                created_at=dt.datetime.combine(entry.booking_date, dt.time.min, tzinfo=dt.UTC),
                status="booked",
            )
            for entry in self.entries
            if entry.credit_debit.upper() == "CRDT"
        ]

    def to_purchase_records(self) -> list[PurchaseRecord]:
        """Convert outgoing debit entries (DBIT) into PurchaseRecord instances."""
        return [
            PurchaseRecord(
                id=entry.reference,
                currency=entry.currency,
                amount=entry.amount,
                created_at=dt.datetime.combine(entry.booking_date, dt.time.min, tzinfo=dt.UTC),
                expected_delivery_date=entry.value_date or entry.booking_date,
                status="settled",
            )
            for entry in self.entries
            if entry.credit_debit.upper() == "DBIT"
        ]

    def currency_summary(self) -> dict[str, dict[str, float]]:
        """Return aggregated totals of credits, debits and net flow per currency."""
        summary: dict[str, dict[str, float]] = {}
        for e in self.entries:
            curr = e.currency
            if curr not in summary:
                summary[curr] = {"credits": 0.0, "debits": 0.0, "net": 0.0}
            if e.credit_debit.upper() == "CRDT":
                summary[curr]["credits"] += e.amount
                summary[curr]["net"] += e.amount
            else:
                summary[curr]["debits"] += e.amount
                summary[curr]["net"] -= e.amount
        return summary


class Camt053Parser:
    """Parser for ISO 20022 Bank-to-Customer Statements (camt.053.001.02 / camt.053.001.08)."""

    @classmethod
    def parse(cls, xml_content: str | bytes) -> CamtStatement:
        statements = cls.parse_all(xml_content)
        return statements[0]

    @classmethod
    def parse_all(cls, xml_content: str | bytes) -> list[CamtStatement]:
        if not xml_content or not str(xml_content).strip():
            raise ConnectorError("Empty or invalid XML document.")

        try:
            root = defused_ET.fromstring(xml_content)
        except Exception as exc:
            raise ConnectorError(f"Invalid XML document: {exc}") from exc

        # Strip namespaces for unified traversal
        cls._strip_namespaces(root)

        stmt_nodes = root.findall(".//Stmt")
        if not stmt_nodes:
            raise ConnectorError("Invalid camt.053 statement: <Stmt> node not found.")

        return [cls._parse_stmt_node(stmt) for stmt in stmt_nodes]

    @classmethod
    def _parse_stmt_node(cls, stmt: ET.Element) -> CamtStatement:
        statement_id = cls._get_text(stmt, "Id", default="UNKNOWN_STMT")
        creation_str = cls._get_text(stmt, "CreDtTm", default="")
        try:
            creation_date = dt.datetime.fromisoformat(creation_str)
        except ValueError:
            creation_date = dt.datetime.now(dt.UTC)

        iban = (
            cls._get_text(stmt, ".//Acct/Id/IBAN")
            or cls._get_text(stmt, ".//Acct/Id/Othr/Id")
            or "UNKNOWN_ACCOUNT"
        )
        currency = cls._get_text(stmt, ".//Acct/Ccy") or "EUR"

        # Balances
        opening_bal: float | None = None
        closing_bal: float | None = None
        for bal_node in stmt.findall("Bal"):
            bal_type = cls._get_text(bal_node, ".//Tp/CdOrPrtry/Cd")
            amt_node = bal_node.find("Amt")
            if amt_node is not None and amt_node.text:
                try:
                    val = float(amt_node.text)
                    cd_ind = cls._get_text(bal_node, "CdtDbtInd")
                    if cd_ind == "DBIT":
                        val = -val
                    if bal_type in ("OPBD", "PRCD"):
                        opening_bal = val
                    elif bal_type in ("CLBD", "CLAV"):
                        closing_bal = val
                except ValueError:
                    pass

        # Entries
        entries: list[CamtEntry] = []
        for ntry in stmt.findall("Ntry"):
            amt_node = ntry.find("Amt")
            if amt_node is None or not amt_node.text:
                continue
            try:
                amt = float(amt_node.text)
            except ValueError:
                continue

            entry_curr = amt_node.attrib.get("Ccy", currency)
            cd_ind = cls._get_text(ntry, "CdtDbtInd", default="CRDT")
            ref = (
                cls._get_text(ntry, ".//AcctSvcrRef")
                or cls._get_text(ntry, "NtryRef")
                or uuid.uuid4().hex[:12]
            )

            booking_date_str = cls._get_text(ntry, ".//BookgDt/Dt") or cls._get_text(
                ntry, ".//BookgDt/DtTm"
            )
            try:
                booking_date = dt.date.fromisoformat(booking_date_str[:10])
            except (ValueError, TypeError):
                booking_date = dt.date.today()

            val_date_str = cls._get_text(ntry, ".//ValDt/Dt")
            val_date = dt.date.fromisoformat(val_date_str[:10]) if val_date_str else None

            counterparty = cls._get_text(ntry, ".//RltdPties/Dbtr/Nm") or cls._get_text(
                ntry, ".//RltdPties/Cdtr/Nm"
            )
            remittance = cls._get_text(ntry, ".//RmtInf/Ustrd")

            entries.append(
                CamtEntry(
                    reference=ref,
                    amount=amt,
                    currency=entry_curr,
                    credit_debit=cd_ind,
                    booking_date=booking_date,
                    value_date=val_date,
                    counterparty_name=counterparty,
                    remittance_info=remittance,
                )
            )

        return CamtStatement(
            statement_id=statement_id,
            iban=iban,
            currency=currency,
            creation_date=creation_date,
            opening_balance=opening_bal,
            closing_balance=closing_bal,
            entries=tuple(entries),
        )

    @staticmethod
    def _strip_namespaces(el: ET.Element) -> None:
        for elem in el.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

    @staticmethod
    def _get_text(parent: ET.Element, path: str, default: str = "") -> str:
        found = parent.find(path)
        return found.text.strip() if (found is not None and found.text) else default


@dataclass(frozen=True, slots=True)
class CreditTransferInstruction:
    end_to_end_id: str
    amount: float
    currency: str
    creditor_name: str
    creditor_iban: str
    creditor_bic: str | None = None
    execution_date: dt.date = field(default_factory=dt.date.today)
    remittance_info: str | None = None


class Pain001Generator:
    """Generator for ISO 20022 Customer Credit Transfer Initiation (pain.001.001.03)."""

    NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"

    @classmethod
    def generate(
        cls,
        initiating_party: str,
        debtor_name: str,
        debtor_iban: str,
        debtor_bic: str | None,
        transfers: list[CreditTransferInstruction],
        message_id: str | None = None,
        payment_info_id: str | None = None,
    ) -> str:
        """Construct a validated, formatted ISO 20022 pain.001.001.03 XML document."""
        if not transfers:
            raise ConnectorError(
                "Cannot generate pain.001 without at least one transfer instruction."
            )

        clean_debtor_iban = debtor_iban.replace(" ", "").upper()
        if len(clean_debtor_iban) < 10:
            raise ConnectorError(f"Invalid debtor IBAN: {debtor_iban!r}")

        for idx, t in enumerate(transfers):
            if t.amount <= 0.0:
                raise ConnectorError(
                    f"Transfer #{idx + 1} ({t.end_to_end_id}) has non-positive amount: {t.amount}"
                )
            clean_creditor_iban = t.creditor_iban.replace(" ", "").upper()
            if len(clean_creditor_iban) < 10:
                raise ConnectorError(
                    f"Transfer #{idx + 1} ({t.end_to_end_id}) has invalid creditor IBAN: {t.creditor_iban!r}"
                )

        msg_id = message_id or f"PARITY-{uuid.uuid4().hex[:12].upper()}"
        pmt_inf_id = payment_info_id or f"PMT-{uuid.uuid4().hex[:8].upper()}"
        ctrl_sum = sum(t.amount for t in transfers)
        nb_txns = len(transfers)
        now_utc = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Root document
        doc = ET.Element(
            "Document",
            {"xmlns": cls.NAMESPACE, "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"},
        )
        cstmr = ET.SubElement(doc, "CstmrCdtTrfInitn")

        # Group Header
        grp_hdr = ET.SubElement(cstmr, "GrpHdr")
        ET.SubElement(grp_hdr, "MsgId").text = msg_id
        ET.SubElement(grp_hdr, "CreDtTm").text = now_utc
        ET.SubElement(grp_hdr, "NbOfTxs").text = str(nb_txns)
        ET.SubElement(grp_hdr, "CtrlSum").text = f"{ctrl_sum:.2f}"
        init_pty = ET.SubElement(grp_hdr, "InitgPty")
        ET.SubElement(init_pty, "Nm").text = initiating_party

        # Payment Information
        pmt_inf = ET.SubElement(cstmr, "PmtInf")
        ET.SubElement(pmt_inf, "PmtInfId").text = pmt_inf_id
        ET.SubElement(pmt_inf, "PmtMtd").text = "TRF"
        ET.SubElement(pmt_inf, "BtchBookg").text = "true"
        ET.SubElement(pmt_inf, "NbOfTxs").text = str(nb_txns)
        ET.SubElement(pmt_inf, "CtrlSum").text = f"{ctrl_sum:.2f}"

        # Execution Date (taking the execution date of the first transfer)
        ET.SubElement(pmt_inf, "ReqdExctnDt").text = transfers[0].execution_date.isoformat()

        # Debtor Info
        dbtr = ET.SubElement(pmt_inf, "Dbtr")
        ET.SubElement(dbtr, "Nm").text = debtor_name

        dbtr_acct = ET.SubElement(pmt_inf, "DbtrAcct")
        dbtr_id = ET.SubElement(dbtr_acct, "Id")
        ET.SubElement(dbtr_id, "IBAN").text = debtor_iban.replace(" ", "").upper()

        if debtor_bic:
            dbtr_agt = ET.SubElement(pmt_inf, "DbtrAgt")
            fin_inst = ET.SubElement(dbtr_agt, "FinInstnId")
            ET.SubElement(fin_inst, "BIC").text = debtor_bic.replace(" ", "").upper()

        # Credit Transfer Transactions
        for tx in transfers:
            tx_node = ET.SubElement(pmt_inf, "CdtTrfTxInf")
            pmt_id = ET.SubElement(tx_node, "PmtId")
            ET.SubElement(pmt_id, "EndToEndId").text = tx.end_to_end_id

            amt = ET.SubElement(tx_node, "Amt")
            instd_amt = ET.SubElement(amt, "InstdAmt", {"Ccy": tx.currency})
            instd_amt.text = f"{tx.amount:.2f}"

            if tx.creditor_bic:
                cdtr_agt = ET.SubElement(tx_node, "CdtrAgt")
                fin_inst = ET.SubElement(cdtr_agt, "FinInstnId")
                ET.SubElement(fin_inst, "BIC").text = tx.creditor_bic.replace(" ", "").upper()

            cdtr = ET.SubElement(tx_node, "Cdtr")
            ET.SubElement(cdtr, "Nm").text = tx.creditor_name

            cdtr_acct = ET.SubElement(tx_node, "CdtrAcct")
            cdtr_id = ET.SubElement(cdtr_acct, "Id")
            ET.SubElement(cdtr_id, "IBAN").text = tx.creditor_iban.replace(" ", "").upper()

            if tx.remittance_info:
                rmt = ET.SubElement(tx_node, "RmtInf")
                ET.SubElement(rmt, "Ustrd").text = tx.remittance_info

        # Pretty print XML string
        rough_string = ET.tostring(doc, encoding="utf-8")
        parsed = minidom.parseString(rough_string)
        return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
