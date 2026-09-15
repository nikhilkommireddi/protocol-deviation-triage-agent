import { jsPDF } from "jspdf";
import type { TriageResult } from "../types";

const MARGIN = 14;
const PAGE_WIDTH = 210;
const MAX_WIDTH = PAGE_WIDTH - MARGIN * 2;

export function generateReportPdf(result: TriageResult): void {
  const doc = new jsPDF();
  let y = MARGIN;

  function heading(text: string) {
    if (y > 270) {
      doc.addPage();
      y = MARGIN;
    }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.text(text, MARGIN, y);
    y += 6;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
  }

  function paragraph(text: string) {
    if (!text) return;
    const lines = doc.splitTextToSize(text, MAX_WIDTH);
    for (const line of lines) {
      if (y > 280) {
        doc.addPage();
        y = MARGIN;
      }
      doc.text(line, MARGIN, y);
      y += 5;
    }
    y += 3;
  }

  function bulletList(items: string[]) {
    for (const item of items) {
      const lines = doc.splitTextToSize(`- ${item}`, MAX_WIDTH - 4);
      for (const line of lines) {
        if (y > 280) {
          doc.addPage();
          y = MARGIN;
        }
        doc.text(line, MARGIN + 2, y);
        y += 5;
      }
    }
    y += 3;
  }

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text("Protocol Deviation Review Memo", MARGIN, y);
  y += 10;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);

  heading("Report Details");
  paragraph(`Report ID: ${result.report_id}`);
  paragraph(`Protocol ID: ${result.protocol_id}    Site ID: ${result.site_id}    Subject ID: ${result.subject_id}`);
  paragraph(`Deviation date: ${result.deviation_date}    Discovery date: ${result.discovery_date}`);
  paragraph(`Status: ${result.status}`);

  heading("Original Report Text");
  paragraph(result.text);

  heading("Classification");
  paragraph(`Category: ${result.category ?? "Not classified"}`);
  if (result.confidence !== null) {
    paragraph(`Confidence: ${(result.confidence * 100).toFixed(0)}%`);
  }

  if (result.capa_guidance) {
    heading("CAPA Guidance");
    paragraph(`Routing team: ${result.capa_guidance.routing_team}`);
    paragraph(`Regulatory reference: ${result.capa_guidance.regulatory_reference}`);
    paragraph("Required CAPA elements:");
    bulletList(result.capa_guidance.required_capa_elements);
  }

  if (result.memo) {
    heading("Memo Summary");
    paragraph(result.memo.summary);

    heading("Root Cause Narrative");
    paragraph(result.memo.root_cause_narrative);

    heading("Regulatory Citation");
    paragraph(result.memo.regulatory_citation);

    heading("Recommended CAPA Actions");
    bulletList(result.memo.recommended_capa_actions);

    heading("Reporting & Ownership");
    paragraph(`Requires expedited reporting: ${result.memo.requires_expedited_reporting ? "Yes" : "No"}`);
    paragraph(`Responsible party: ${result.memo.responsible_party}`);
    paragraph(`Target resolution date: ${result.memo.target_resolution_date}`);
    if (result.memo.reviewer_note) {
      paragraph(`Reviewer note: ${result.memo.reviewer_note}`);
    }
  }

  doc.save(`deviation-report-${result.report_id.slice(0, 8)}.pdf`);
}
