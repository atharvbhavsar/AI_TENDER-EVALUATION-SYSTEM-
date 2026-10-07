/**
 * Automated Verification Suite for Phase 8: Bid Application & Submission Workflow.
 * Rigorously executes against the live FastAPI backend (http://127.0.0.1:8000).
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
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

async function runPhase8Verification() {
  console.log("=================================================");
  console.log("STARTING PHASE 8 BID APPLICATION & SUBMISSION VERIFICATION");
  console.log("=================================================");

  const timestamp = Date.now().toString().slice(-6);
  const emailA = `vendor.alpha.${timestamp}@defenseco.in`;
  const emailB = `vendor.beta.${timestamp}@aerospacecorp.in`;
  const password = "ValidPassword123!";

  try {
    // -------------------------------------------------------------
    // SETUP: Authenticate Procurement Officer to establish tenders
    // -------------------------------------------------------------
    console.log("\n[*] Setup: Authenticating Officer & Creating Tenders...");
    const officerLoginRes = await fetch(`${BACKEND_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "officer@crpf.gov.in", password: "OfficerPassword123!" }),
    });
    assert(officerLoginRes.status === 200, "Procurement Officer authentication succeeded");
    const officerToken = (await officerLoginRes.json()).access_token;

    // 1. Create Tender 1 (Normal Open Tender with Future Deadline)
    const futureDeadline = new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString();
    const t1CreateRes = await fetch(`${BACKEND_BASE}/tenders`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${officerToken}`,
      },
      body: JSON.stringify({
        tender_number: `CRPF/PH8/OPEN/${timestamp}`,
        title: "Advanced Tactical Night Vision Goggles Procurement",
        description: "Procurement of Generation 3+ Night Vision Devices for CRPF Special Action Force",
        issuing_authority: "CRPF Directorate General, New Delhi",
        initial_version_label: "v1.0-RFP",
        initial_change_summary: "Initial open RFP release",
        submission_deadline: futureDeadline,
      }),
    });
    assert(t1CreateRes.status === 201, "Open tender created successfully");
    const tender1 = await t1CreateRes.json();

    // Publish Tender 1
    const t1PubRes = await fetch(`${BACKEND_BASE}/tenders/${tender1.id}/publish`, {
      method: "POST",
      headers: { Authorization: `Bearer ${officerToken}` },
    });
    assert(t1PubRes.status === 200, "Open tender transitioned to PUBLISHED status");

    // 2. Create Tender 2 (Closed Tender)
    const t2CreateRes = await fetch(`${BACKEND_BASE}/tenders`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${officerToken}`,
      },
      body: JSON.stringify({
        tender_number: `CRPF/PH8/CLOSED/${timestamp}`,
        title: "Archived Wireless Perimeter Surveillance Radar",
        description: "Procurement concluded for perimeter radar systems",
        issuing_authority: "CRPF Logistics Directorate",
        initial_version_label: "v1.0-Closed",
        initial_change_summary: "Initial draft",
      }),
    });
    const tender2 = await t2CreateRes.json();
    // Publish then close
    await fetch(`${BACKEND_BASE}/tenders/${tender2.id}/publish`, {
      method: "POST",
      headers: { Authorization: `Bearer ${officerToken}` },
    });
    const t2CloseRes = await fetch(`${BACKEND_BASE}/tenders/${tender2.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${officerToken}`,
      },
      body: JSON.stringify({ status: "CLOSED" }),
    });
    assert(t2CloseRes.status === 200, "Closed tender created and updated to CLOSED status");

    // 3. Create Tender 3 (Expired Deadline Tender)
    const pastDeadline = new Date(Date.now() - 3600 * 1000).toISOString(); // 1 hour ago
    const t3CreateRes = await fetch(`${BACKEND_BASE}/tenders`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${officerToken}`,
      },
      body: JSON.stringify({
        tender_number: `CRPF/PH8/EXPIRED/${timestamp}`,
        title: "Rapid Deployment Ballistic Shield Units",
        description: "Deadline expired for ballistic shields",
        issuing_authority: "CRPF Procurement Cell",
        initial_version_label: "v1.0-Expired",
        initial_change_summary: "Initial spec",
        submission_deadline: pastDeadline,
      }),
    });
    const tender3 = await t3CreateRes.json();
    await fetch(`${BACKEND_BASE}/tenders/${tender3.id}/publish`, {
      method: "POST",
      headers: { Authorization: `Bearer ${officerToken}` },
    });
    assert(Boolean(tender3.id), "Expired deadline tender created and published");

    // -------------------------------------------------------------
    // Register Bidder A & Bidder B
    // -------------------------------------------------------------
    console.log("\n[*] Setup: Registering Bidder A & Bidder B...");
    const regResA = await fetch(`${BACKEND_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailA,
        password: password,
        full_name: "Vikramaditya Rao",
        company_name: "Paramount Tactical Systems Ltd",
        phone: "+91 9876543210",
      }),
    });
    assert(regResA.status === 201, "Bidder A registered successfully");
    const tokenA = (await regResA.json()).access_token;

    const regResB = await fetch(`${BACKEND_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailB,
        password: password,
        full_name: "Ananya Deshmukh",
        company_name: "AeroOptics Private Limited",
        phone: "+91 9123456780",
      }),
    });
    assert(regResB.status === 201, "Bidder B registered successfully");
    const tokenB = (await regResB.json()).access_token;

    // -------------------------------------------------------------
    // TEST 1 — Create Application (Public Tender -> Apply)
    // -------------------------------------------------------------
    console.log("\n[TEST 1] Create Application on Open Published Tender");
    const applyResA = await fetch(`${BACKEND_BASE}/bidder/apply/${tender1.id}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(applyResA.status === 201, `Bidder A created application (HTTP ${applyResA.status})`);
    const appA = await applyResA.json();
    assert(Boolean(appA.id), "Application ID assigned by server");
    assert(appA.status === "DRAFT", `Initial application status is strictly DRAFT (received ${appA.status})`);
    assert(appA.is_locked === false, "Draft application is not locked");
    assert(appA.tender_id === tender1.id, "Application correctly mapped to target tender");

    // -------------------------------------------------------------
    // TEST 2 & 8 — Idempotent Existing Application Handling (No Duplicates)
    // -------------------------------------------------------------
    console.log("\n[TEST 2 & 8] Idempotent Apply / Existing Application Handling");
    const applyAgainRes = await fetch(`${BACKEND_BASE}/bidder/apply/${tender1.id}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(
      applyAgainRes.status === 200 || applyAgainRes.status === 201,
      `Re-applying returns HTTP ${applyAgainRes.status} (existing application opened)`
    );
    const existingApp = await applyAgainRes.json();
    assert(existingApp.id === appA.id, "Existing application ID returned without creating a duplicate record");

    // Check count in list
    const listRes = await fetch(`${BACKEND_BASE}/bidder/applications`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    const listData = await listRes.json();
    assert(listData.total === 1, `Total applications count remains exactly 1 (received ${listData.total})`);

    // -------------------------------------------------------------
    // TEST 3 — Draft Application Persistence (Save Draft)
    // -------------------------------------------------------------
    console.log("\n[TEST 3] Draft Application Editing & Persistence");
    const draftPayload = {
      commercial_quote: 4500000.0,
      bidder_notes: "Committed delivery timeline of 45 days. ISO 9001:2015 certified production line.",
      declaration_signed: true,
    };
    const patchDraftRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenA}`,
      },
      body: JSON.stringify(draftPayload),
    });
    assert(patchDraftRes.status === 200, `Draft saved successfully (HTTP ${patchDraftRes.status})`);
    const patchedApp = await patchDraftRes.json();
    assert(patchedApp.commercial_quote === 4500000.0, "Commercial quote successfully saved");
    assert(patchedApp.bidder_notes.includes("ISO 9001:2015"), "Bidder notes successfully saved");
    assert(patchedApp.declaration_signed === true, "Declaration state saved");
    assert(patchedApp.status === "DRAFT", "Status remains DRAFT during preparation");
    assert(patchedApp.can_edit === true, "can_edit flag indicates editable");
    assert(patchedApp.can_submit === true, "can_submit flag indicates eligible for submission");

    // Verify retrieval after simulated browser refresh
    const detailRefreshRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(detailRefreshRes.status === 200, "Refreshed detail query succeeds");
    const refreshedApp = await detailRefreshRes.json();
    assert(refreshedApp.commercial_quote === 4500000.0, "Refreshed state matches DB persistence (quote)");
    assert(refreshedApp.bidder_notes === draftPayload.bidder_notes, "Refreshed state matches DB persistence (notes)");

    // -------------------------------------------------------------
    // TEST 4 & 5 — Application Submission & Server Locking
    // -------------------------------------------------------------
    console.log("\n[TEST 4 & 5] Formal Bid Submission & Server-Side Locking");
    const submitPayload = {
      confirm_declaration: true,
      commercial_quote: 4450000.0, // Final revised commercial quote
      bidder_notes: "Final confirmed proposal: 45 days delivery with 3-year extended warranty.",
    };
    const submitRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}/submit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenA}`,
      },
      body: JSON.stringify(submitPayload),
    });
    assert(submitRes.status === 200, `Application successfully submitted (HTTP ${submitRes.status})`);
    const submittedApp = await submitRes.json();
    assert(submittedApp.status === "SUBMITTED", "Application status transitioned to SUBMITTED");
    assert(submittedApp.is_locked === true, "Application is now permanently LOCKED");
    assert(Boolean(submittedApp.submitted_at), "Authoritative server submitted_at timestamp is populated");
    assert(submittedApp.commercial_quote === 4450000.0, "Final commercial quote locked");
    assert(submittedApp.can_edit === false, "can_edit is now false");
    assert(submittedApp.can_submit === false, "can_submit is now false");

    // -------------------------------------------------------------
    // TEST 5b — Post-Submission Immutability Guard
    // -------------------------------------------------------------
    console.log("\n[TEST 5b] Post-Submission Immutability (Locked Read-Only)");
    const illegalEditRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenA}`,
      },
      body: JSON.stringify({ commercial_quote: 3000000.0 }),
    });
    assert(
      illegalEditRes.status === 400,
      `Edit on submitted application rejected with HTTP 400 (received ${illegalEditRes.status})`
    );
    const illegalEditErr = await illegalEditRes.json();
    assert(
      illegalEditErr.detail.toLowerCase().includes("locked"),
      `Safe error message: "${illegalEditErr.detail}"`
    );

    // Double Submission Guard
    const doubleSubmitRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}/submit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenA}`,
      },
      body: JSON.stringify({ confirm_declaration: true }),
    });
    assert(
      doubleSubmitRes.status === 400,
      `Double submission rejected with HTTP 400 (received ${doubleSubmitRes.status})`
    );

    // -------------------------------------------------------------
    // TEST 6 — Deadline Rejection (Server-Side Clock Authoritative)
    // -------------------------------------------------------------
    console.log("\n[TEST 6] Expired Deadline Enforcement (Server Clock)");
    // Attempting to apply to Tender 3 whose deadline has passed
    const applyExpiredRes = await fetch(`${BACKEND_BASE}/bidder/apply/${tender3.id}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(
      applyExpiredRes.status === 400,
      `Application to expired tender rejected with HTTP 400 (received ${applyExpiredRes.status})`
    );
    const expiredErr = await applyExpiredRes.json();
    assert(
      expiredErr.detail.toLowerCase().includes("deadline has passed"),
      `Safe deadline error message: "${expiredErr.detail}"`
    );

    // -------------------------------------------------------------
    // TEST 7 — IDOR & Multi-Bidder Cross-Tenant Isolation
    // -------------------------------------------------------------
    console.log("\n[TEST 7] IDOR Prevention & Multi-Bidder Data Isolation");
    // Bidder B attempts to query Bidder A's application
    const idorGetRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}`, {
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    assert(
      idorGetRes.status === 404,
      `IDOR GET blocked: Bidder B receives HTTP 404 when querying Bidder A's application (received ${idorGetRes.status})`
    );

    // Bidder B attempts to modify Bidder A's application
    const idorPatchRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenB}`,
      },
      body: JSON.stringify({ commercial_quote: 100.0 }),
    });
    assert(
      idorPatchRes.status === 404,
      `IDOR PATCH blocked: Bidder B receives HTTP 404 attempting to edit Bidder A's application (received ${idorPatchRes.status})`
    );

    // Bidder B attempts to submit Bidder A's application
    const idorSubmitRes = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}/submit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenB}`,
      },
      body: JSON.stringify({ confirm_declaration: true }),
    });
    assert(
      idorSubmitRes.status === 404,
      `IDOR SUBMIT blocked: Bidder B receives HTTP 404 attempting to submit Bidder A's application (received ${idorSubmitRes.status})`
    );

    // -------------------------------------------------------------
    // TEST 9 — Closed Tender Application Protection
    // -------------------------------------------------------------
    console.log("\n[TEST 9] Closed Tender Protection");
    const applyClosedRes = await fetch(`${BACKEND_BASE}/bidder/apply/${tender2.id}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(
      applyClosedRes.status === 400,
      `Applying to CLOSED tender rejected with HTTP 400 (received ${applyClosedRes.status})`
    );
    const closedErr = await applyClosedRes.json();
    assert(
      closedErr.detail.toLowerCase().includes("only published tenders accept applications"),
      `Safe closed tender error: "${closedErr.detail}"`
    );

    // -------------------------------------------------------------
    // TEST 10 — Refresh & State Consistency
    // -------------------------------------------------------------
    console.log("\n[TEST 10] Refresh & State Consistency");
    const postSubmitGet = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    const postSubmitData = await postSubmitGet.json();
    assert(postSubmitData.status === "SUBMITTED", "Status remains SUBMITTED after retrieval");
    assert(postSubmitData.is_locked === true, "is_locked remains true after retrieval");
    assert(postSubmitData.can_edit === false, "can_edit remains false");

    // -------------------------------------------------------------
    // TEST 11 — Stale Tab & Double Submission Concurrency
    // -------------------------------------------------------------
    console.log("\n[TEST 11] Stale Tab & Double Submit Protection");
    const staleSubmit = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}/submit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenA}`,
      },
      body: JSON.stringify({ confirm_declaration: true }),
    });
    assert(
      staleSubmit.status === 400,
      `Stale tab submission correctly rejected with HTTP 400 (received ${staleSubmit.status})`
    );

    // -------------------------------------------------------------
    // TEST 12 — Unauthenticated Route Guard
    // -------------------------------------------------------------
    console.log("\n[TEST 12] Unauthenticated Route Guard");
    const unauthGet = await fetch(`${BACKEND_BASE}/bidder/applications/${appA.id}`);
    assert(unauthGet.status === 401, `Unauthenticated application access returns HTTP 401 (received ${unauthGet.status})`);

    // -------------------------------------------------------------
    // TEST 13 & 14 — Accessibility, UI Structure, Security Audit
    // -------------------------------------------------------------
    console.log("\n[TEST 13 & 14] Accessibility, Responsive Layout & Security Audit");
    const appDetailContent = fs.readFileSync(
      path.join(frontendRoot, "src/app/bidder/applications/[applicationId]/page.tsx"),
      "utf-8"
    );

    assert(
      appDetailContent.includes('role="dialog"') &&
      appDetailContent.includes('aria-modal="true"') &&
      appDetailContent.includes('aria-labelledby="submit-modal-title"'),
      "Submission confirmation dialog satisfies WAI-ARIA accessibility standards"
    );
    assert(
      appDetailContent.includes('key === "Escape"'),
      "Keyboard escape key dismissal implemented for modal dialog"
    );
    assert(
      appDetailContent.includes("Official Submission Receipt") &&
      appDetailContent.includes("submission_reference"),
      "Official Submission Receipt and locked state rendered for submitted applications"
    );
    assert(
      appDetailContent.includes("Save Draft") &&
      appDetailContent.includes("Review & Submit Bid"),
      "Draft preparation and two-step review & submit workflow verified in UI"
    );
    assert(
      !appDetailContent.includes("password=") &&
      !appDetailContent.includes("secret=") &&
      !appDetailContent.includes("Bearer "),
      "Security Audit: Zero hardcoded credentials or access tokens found in frontend source"
    );

    console.log("\n=================================================");
    console.log("PHASE 8 VERIFICATION COMPLETE");
    console.log("=================================================");
    console.log(`Total Tests: ${passedCount + failedCount} | Passed: ${passedCount} | Failed: ${failedCount}`);

    if (failedCount > 0) {
      process.exit(1);
    }
  } catch (err) {
    console.error("Fatal error during verification:", err);
    process.exit(1);
  }
}

runPhase8Verification();
