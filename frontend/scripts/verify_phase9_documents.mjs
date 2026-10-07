/**
 * Automated Verification Suite for Phase 9: Bidder Document Upload & Document Management.
 * Rigorously executes against the live FastAPI backend (http://127.0.0.1:8000).
 */

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const BACKEND_BASE = "http://127.0.0.1:8000/api/v1";

let passedCount = 0;
let failedCount = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`[PASS] ${message}`);
    passedCount++;
  } else {
    console.error(`[FAIL] ${message}`);
    failedCount++;
  }
}

function seedApprovedCriteria(tenderId, versionId) {
  const scriptPath = path.resolve(__dirname, "../../backend/scripts/_tmp_seed_criteria.py");
  const pyContent = `
import sys, os
sys.path.insert(0, r"d:\\tender\\backend")
import uuid
from app.db.session import SessionLocal
from app.db.models.tender_criterion import TenderCriterion, ApprovalStatus, CriterionCategory, RequirementType, ExtractionStatus

db = SessionLocal()
try:
    c1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=uuid.UUID('${versionId}'),
        criterion_code="DOC-GST-01",
        name="GST Registration Certificate",
        description="Authoritative GSTIN verification document.",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        required_evidence="Valid GST Registration Certificate (Form REG-06)",
        source_clause="Section 4.1.1 GST Statutory Mandate",
        model_name="gemini-2.5-flash",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        extraction_status=ExtractionStatus.EXTRACTED,
    )
    c2 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=uuid.UUID('${versionId}'),
        criterion_code="DOC-PAN-02",
        name="Permanent Account Number (PAN)",
        description="Company PAN Card copy.",
        category=CriterionCategory.COMPLIANCE,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        required_evidence="PAN Card Copy",
        source_clause="Section 4.1.2 Income Tax Act Mandate",
        model_name="gemini-2.5-flash",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        extraction_status=ExtractionStatus.EXTRACTED,
    )
    db.add(c1)
    db.add(c2)
    db.commit()
    print(f"{c1.id},{c2.id}")
finally:
    db.close()
`;
  fs.writeFileSync(scriptPath, pyContent, "utf-8");
  try {
    const out = execSync(`d:\\tender\\backend\\.venv\\Scripts\\python.exe "${scriptPath}"`, {
      cwd: "d:\\tender\\backend",
    })
      .toString()
      .trim();
    const [crit1Id, crit2Id] = out.split(",");
    return { crit1Id, crit2Id };
  } finally {
    if (fs.existsSync(scriptPath)) {
      fs.unlinkSync(scriptPath);
    }
  }
}

// Helper to create minimal valid PDF binary
function createDummyPdf(text = "CRPF Tender Procurement Evidence") {
  const content = `%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n% ${text}`;
  return Buffer.from(content, "utf-8");
}

// Helper to create minimal valid PNG binary
function createDummyPng() {
  const pngHeader = Buffer.from([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, // PNG Signature
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, // IHDR header
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, // 1x1 dimensions
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, // RGBA, CRC
    0x89, 0x00, 0x00, 0x00, 0x0a, 0x49, 0x44, 0x41, // IDAT header
    0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00,
    0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, // IEND
    0x42, 0x60, 0x82,
  ]);
  return pngHeader;
}

async function runPhase9Verification() {
  console.log("=================================================");
  console.log("STARTING PHASE 9 BIDDER DOCUMENT MANAGEMENT VERIFICATION");
  console.log("=================================================");

  const timestamp = Date.now().toString().slice(-6);
  const emailA = `vendor.doc.alpha.${timestamp}@defenseco.in`;
  const emailB = `vendor.doc.beta.${timestamp}@aerospacecorp.in`;
  const password = "ValidPassword123!";

  try {
    // -------------------------------------------------------------
    // SETUP: Authenticate Officer & Create Tender with Criteria
    // -------------------------------------------------------------
    console.log("\n[*] Setup: Authenticating Officer & Creating Published Tender with Criteria...");
    const officerLoginRes = await fetch(`${BACKEND_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "officer@crpf.gov.in", password: "OfficerPassword123!" }),
    });
    assert(officerLoginRes.status === 200, "Procurement Officer authentication succeeded");
    const officerToken = (await officerLoginRes.json()).access_token;

    // Create Published Tender with Future Deadline
    const futureDeadline = new Date(Date.now() + 10 * 24 * 3600 * 1000).toISOString();
    const tCreateRes = await fetch(`${BACKEND_BASE}/tenders`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${officerToken}`,
      },
      body: JSON.stringify({
        tender_number: `CRPF/PH9/DOC/${timestamp}`,
        title: `Procurement of Security Gear Phase 9 - Ref ${timestamp}`,
        description: "Standard tactical equipment procurement with mandatory certifications.",
        issuing_authority: "CRPF Logistics Directorate",
        estimated_value: 8500000,
        submission_deadline: futureDeadline,
      }),
    });
    assert(tCreateRes.status === 201, "Tender created successfully with submission deadline");
    const tender = await tCreateRes.json();
    const tenderId = tender.id;
    const versionId = tender.active_version.id;

    // Seed 2 Approved Criteria under active version
    const { crit1Id, crit2Id } = seedApprovedCriteria(tenderId, versionId);
    assert(Boolean(crit1Id && crit2Id), "Criterion 1 (GST) and Criterion 2 (PAN) seeded and approved");
    const crit1 = { id: crit1Id };
    const crit2 = { id: crit2Id };

    // Publish Tender
    const pubRes = await fetch(`${BACKEND_BASE}/tenders/${tenderId}/publish`, {
      method: "POST",
      headers: { Authorization: `Bearer ${officerToken}` },
    });
    assert(pubRes.status === 200, "Tender published successfully");

    // -------------------------------------------------------------
    // REGISTER BIDDER A & BIDDER B
    // -------------------------------------------------------------
    console.log("\n[*] Setup: Registering Bidder A & Bidder B...");
    const regARes = await fetch(`${BACKEND_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailA,
        password,
        full_name: "Alpha Defense Rep",
        company_name: "Alpha Defense Systems Ltd",
        phone: "+919876543210",
        role: "BIDDER",
      }),
    });
    assert(regARes.status === 201, "Bidder A registered");
    const tokenA = (await regARes.json()).access_token;

    const regBRes = await fetch(`${BACKEND_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailB,
        password,
        full_name: "Beta Aerospace Rep",
        company_name: "Beta Aerospace Tech Ltd",
        phone: "+919876543211",
        role: "BIDDER",
      }),
    });
    assert(regBRes.status === 201, "Bidder B registered");
    const tokenB = (await regBRes.json()).access_token;

    // Bidder A applies to Tender
    const applyARes = await fetch(`${BACKEND_BASE}/bidder/apply/${tenderId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(applyARes.status === 201, "Bidder A applied to tender");
    const appA = await applyARes.json();
    const appAId = appA.id;

    // Bidder B applies to Tender
    const applyBRes = await fetch(`${BACKEND_BASE}/bidder/apply/${tenderId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    assert(applyBRes.status === 201, "Bidder B applied to tender");
    const appB = await applyBRes.json();
    const appBId = appB.id;

    // -------------------------------------------------------------
    // TEST 1 — Valid Document Upload (PDF & PNG)
    // -------------------------------------------------------------
    console.log("\n--- TEST 1: Valid Document Upload ---");
    const pdfBytes1 = createDummyPdf("Alpha Defense GST Registration REG-06 Certificate");
    const form1 = new FormData();
    form1.append("file", new Blob([pdfBytes1], { type: "application/pdf" }), "GST_Registration_Certificate.pdf");
    form1.append("criterion_id", crit1.id);
    form1.append("document_type", "DIGITAL_PDF");

    const up1Res = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
      body: form1,
    });
    assert(up1Res.status === 201, "Bidder A uploaded valid GST PDF for Criterion 1");
    const doc1 = await up1Res.json();
    assert(doc1.filename === "GST_Registration_Certificate.pdf", "Filename stored cleanly");
    assert(doc1.criterion_id === crit1.id, "Criterion ID correctly associated");
    assert(doc1.bid_submission_id === appAId, "Application ID correctly associated");
    assert(doc1.sha256_hash && doc1.sha256_hash.length === 64, "Cryptographic SHA-256 computed");

    // Upload PNG for Criterion 2
    const pngBytes = createDummyPng();
    const form2 = new FormData();
    form2.append("file", new Blob([pngBytes], { type: "image/png" }), "Company_PAN_Card.png");
    form2.append("criterion_id", crit2.id);
    form2.append("document_type", "PHOTOGRAPH");

    const up2Res = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
      body: form2,
    });
    assert(up2Res.status === 201, "Bidder A uploaded valid PAN PNG for Criterion 2");
    const doc2 = await up2Res.json();
    assert(doc2.criterion_id === crit2.id, "Criterion 2 ID correctly associated");

    // Upload General Supporting Document (No criterion_id)
    const pdfBytesGen = createDummyPdf("Alpha Defense Power of Attorney and Board Resolution");
    const formGen = new FormData();
    formGen.append("file", new Blob([pdfBytesGen], { type: "application/pdf" }), "Power_Of_Attorney.pdf");

    const upGenRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
      body: formGen,
    });
    assert(upGenRes.status === 201, "Bidder A uploaded general supporting document without criterion_id");
    const docGen = await upGenRes.json();
    assert(docGen.criterion_id === null, "General document has criterion_id = null");

    // -------------------------------------------------------------
    // TEST 2 — Invalid File Rejection (Unsupported extension / executable)
    // -------------------------------------------------------------
    console.log("\n--- TEST 2: Invalid File Rejection ---");
    const exeBytes = Buffer.from("MZ\x90\x00\x03\x00\x00\x00BinaryExeContent");
    const formExe = new FormData();
    formExe.append("file", new Blob([exeBytes], { type: "application/x-msdownload" }), "malicious_script.exe");

    const upExeRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
      body: formExe,
    });
    assert(upExeRes.status === 400, "Disallowed executable extension '.exe' rejected with HTTP 400");

    // -------------------------------------------------------------
    // TEST 3 — Corrupted / Mismatched Magic Bytes Rejection
    // -------------------------------------------------------------
    console.log("\n--- TEST 3: Corrupted File & MIME Spoofing Rejection ---");
    const fakePdfBytes = Buffer.from("NOT_A_REAL_PDF_HEADER_THIS_IS_PLAIN_TEXT");
    const formFakePdf = new FormData();
    formFakePdf.append("file", new Blob([fakePdfBytes], { type: "application/pdf" }), "spoofed_cert.pdf");

    const upFakeRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
      body: formFakePdf,
    });
    assert(upFakeRes.status === 400, "Corrupted file claiming .pdf without %PDF- magic bytes rejected with HTTP 400");

    // -------------------------------------------------------------
    // TEST 4 — Document Listing Persistence & Application Detail
    // -------------------------------------------------------------
    console.log("\n--- TEST 4: Document Listing & Completeness ---");
    const listRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "GET",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(listRes.status === 200, "List documents endpoint returned HTTP 200");
    const docList = await listRes.json();
    assert(docList.length === 3, "Exactly 3 documents listed for Application A");

    // Check application detail endpoint includes documents
    const appDetailRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(appDetailRes.status === 200, "Get application detail returned HTTP 200");
    const appDetail = await appDetailRes.json();
    assert(appDetail.documents.length === 3, "Application detail response includes all 3 documents");
    assert(appDetail.documents_count === 3, "Application detail documents_count is 3");

    // -------------------------------------------------------------
    // TEST 5 — Secure Document Download / Binary Stream
    // -------------------------------------------------------------
    console.log("\n--- TEST 5: Secure Document Stream Download ---");
    const dlRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents/${doc1.id}/download`, {
      method: "GET",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(dlRes.status === 200, "Secure document stream returned HTTP 200");
    assert(dlRes.headers.get("content-type") === "application/pdf", "Content-Type matches PDF");
    assert(dlRes.headers.get("content-disposition")?.includes("GST_Registration_Certificate.pdf"), "Content-Disposition includes filename");

    const downloadedBuffer = Buffer.from(await dlRes.arrayBuffer());
    const downloadedHash = crypto.createHash("sha256").update(downloadedBuffer).digest("hex");
    assert(downloadedHash === doc1.sha256_hash, "Downloaded binary cryptographic SHA-256 matches stored metadata");

    // -------------------------------------------------------------
    // TEST 6 — Document Replacement (Re-uploading against Criterion 1)
    // -------------------------------------------------------------
    console.log("\n--- TEST 6: Document Replacement ---");
    const pdfBytesUpdated = createDummyPdf("Alpha Defense Updated GST Registration REG-06 V2");
    const formUpdate = new FormData();
    formUpdate.append("file", new Blob([pdfBytesUpdated], { type: "application/pdf" }), "GST_Certificate_v2.pdf");
    formUpdate.append("criterion_id", crit1.id);

    const upUpdateRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
      body: formUpdate,
    });
    assert(upUpdateRes.status === 201, "Document replaced for Criterion 1 successfully");
    const docUpdated = await upUpdateRes.json();
    assert(docUpdated.filename === "GST_Certificate_v2.pdf", "Replaced filename is GST_Certificate_v2.pdf");
    assert(docUpdated.id !== doc1.id, "New document entity created with unique UUID");

    // Verify total count is still 3 (replaced old one)
    const listAfterReplaceRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "GET",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    const docsAfterReplace = await listAfterReplaceRes.json();
    assert(docsAfterReplace.length === 3, "Total document count remains 3 after replacement");

    // -------------------------------------------------------------
    // TEST 7 — Document Deletion
    // -------------------------------------------------------------
    console.log("\n--- TEST 7: Document Deletion ---");
    const delRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents/${docGen.id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(delRes.status === 200, "General document deleted successfully");
    const delJson = await delRes.json();
    assert(delJson.success === true, "Delete confirmation returns success: true");

    const listAfterDelRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "GET",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    const docsAfterDel = await listAfterDelRes.json();
    assert(docsAfterDel.length === 2, "Document count reduced to 2 after deletion");

    // -------------------------------------------------------------
    // TEST 8 — IDOR Security: Bidder B cannot access or modify Bidder A's Documents
    // -------------------------------------------------------------
    console.log("\n--- TEST 8: Strict Cross-Bidder IDOR Protection ---");
    // Bidder B attempts to download Bidder A's document
    const idorDlRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents/${doc2.id}/download`, {
      method: "GET",
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    assert(idorDlRes.status === 404, "Bidder B downloading Bidder A document rejected with HTTP 404");

    // Bidder B attempts to delete Bidder A's document
    const idorDelRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents/${doc2.id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    assert(idorDelRes.status === 404, "Bidder B deleting Bidder A document rejected with HTTP 404");

    // Bidder B attempts to list Bidder A's documents
    const idorListRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "GET",
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    assert(idorListRes.status === 404, "Bidder B listing Bidder A documents rejected with HTTP 404");

    // -------------------------------------------------------------
    // TEST 9 — Application Mismatch Protection
    // -------------------------------------------------------------
    console.log("\n--- TEST 9: Application Mismatch Protection ---");
    const formMismatch = new FormData();
    formMismatch.append("file", new Blob([pdfBytes1], { type: "application/pdf" }), "test.pdf");
    const mismatchRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appBId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` }, // Bidder A token to Bidder B's application
      body: formMismatch,
    });
    assert(mismatchRes.status === 404, "Bidder A uploading to Bidder B's application rejected with HTTP 404");

    // -------------------------------------------------------------
    // TEST 10 — Submitted Application Immutability (Locking)
    // -------------------------------------------------------------
    console.log("\n--- TEST 10: Submitted Application Document Locking ---");
    // Formally submit Bidder A's application
    const submitRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/submit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenA}`,
      },
      body: JSON.stringify({
        confirm_declaration: true,
        commercial_quote: 7500000,
        bidder_notes: "Final compliance response with all verified proofs attached.",
      }),
    });
    assert(submitRes.status === 200, "Bidder A application formally submitted and sealed");

    // Attempt to upload document to submitted application
    const formPostSubmit = new FormData();
    formPostSubmit.append("file", new Blob([pdfBytes1], { type: "application/pdf" }), "late_doc.pdf");
    const postSubmitUpRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
      body: formPostSubmit,
    });
    assert(postSubmitUpRes.status === 400, "Document upload to submitted/locked application rejected with HTTP 400");

    // Attempt to delete document from submitted application
    const postSubmitDelRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents/${doc2.id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(postSubmitDelRes.status === 400, "Document deletion from submitted/locked application rejected with HTTP 400");

    // Verification that submitted documents can still be downloaded for auditing
    const auditDlRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents/${doc2.id}/download`, {
      method: "GET",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(auditDlRes.status === 200, "Submitted/sealed documents remain downloadable for auditing and record verification");

    // -------------------------------------------------------------
    // TEST 11 — Expired Tender Deadline Lock
    // -------------------------------------------------------------
    console.log("\n--- TEST 11: Expired Tender Deadline Lock ---");
    // Create tender with expired deadline
    const pastDeadline = new Date(Date.now() - 3600 * 1000).toISOString();
    const tExpiredRes = await fetch(`${BACKEND_BASE}/tenders`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${officerToken}`,
      },
      body: JSON.stringify({
        tender_number: `CRPF/PH9/EXPIRED/${timestamp}`,
        title: `Expired Tender Phase 9 - Ref ${timestamp}`,
        description: "Tender with passed deadline.",
        issuing_authority: "CRPF Directorate",
        estimated_value: 3000000,
        submission_deadline: pastDeadline,
      }),
    });
    const tenderExp = await tExpiredRes.json();

    // Publish expired tender
    await fetch(`${BACKEND_BASE}/tenders/${tenderExp.id}/publish`, {
      method: "POST",
      headers: { Authorization: `Bearer ${officerToken}` },
    });

    // Attempting to apply to expired tender must be rejected
    const applyExpRes = await fetch(`${BACKEND_BASE}/bidder/apply/${tenderExp.id}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    assert(applyExpRes.status === 400, "Applying to expired tender rejected with HTTP 400");

    // -------------------------------------------------------------
    // TEST 12 — Unauthenticated Access
    // -------------------------------------------------------------
    console.log("\n--- TEST 12: Unauthenticated Access ---");
    const unauthRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appAId}/documents`, {
      method: "GET",
    });
    assert(unauthRes.status === 401, "Unauthenticated document list rejected with HTTP 401");

    // -------------------------------------------------------------
    // SUMMARY
    // -------------------------------------------------------------
    console.log("\n=================================================");
    console.log(`PHASE 9 VERIFICATION COMPLETE: ${passedCount} PASSED, ${failedCount} FAILED`);
    console.log("=================================================");

    if (failedCount > 0) {
      process.exit(1);
    }
  } catch (err) {
    console.error("FATAL ERROR in Phase 9 verification:", err);
    process.exit(1);
  }
}

runPhase9Verification();
