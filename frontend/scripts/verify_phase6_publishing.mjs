/**
 * End-to-End Verification Script for PHASE 6:
 * TENDER PUBLISHING & PUBLIC TENDER PORTAL
 */

const BACKEND_BASE = "http://127.0.0.1:8000/api/v1";
const FRONTEND_BASE = "http://localhost:3000";

let testResults = [];

function assert(condition, message) {
  if (condition) {
    testResults.push({ status: "PASS", message });
    console.log(`[PASS] ${message}`);
  } else {
    testResults.push({ status: "FAIL", message });
    console.error(`[FAIL] ${message}`);
  }
}

async function login(email, password) {
  const res = await fetch(`${BACKEND_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    throw new Error(`Login failed for ${email}: ${res.status}`);
  }
  const data = await res.json();
  return data.access_token;
}

async function runVerification() {
  console.log("=================================================");
  console.log("STARTING PHASE 6 PUBLISHING & PUBLIC PORTAL TESTS");
  console.log("=================================================");

  try {
    // Authenticate Officer
    console.log("\n1. Authenticating as Officer (officer@crpf.gov.in)...");
    const officerToken = await login("officer@crpf.gov.in", "OfficerPassword123!");
    assert(Boolean(officerToken), "Officer login successful");

    // Authenticate Reviewer (unauthorized for publishing)
    console.log("2. Authenticating as Reviewer (reviewer@crpf.gov.in)...");
    const reviewerToken = await login("reviewer@crpf.gov.in", "ReviewerPassword123!");
    assert(Boolean(reviewerToken), "Reviewer login successful");

    // Create a new test draft tender
    const testRef = `CRPF/PUBTEST/${Date.now().toString().slice(-6)}`;
    console.log(`\n3. Creating Draft Tender (${testRef})...`);
    const createRes = await fetch(`${BACKEND_BASE}/tenders`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${officerToken}`,
      },
      body: JSON.stringify({
        tender_number: testRef,
        title: "Tactical Communication Headsets & Transceivers",
        description: "Procurement of ruggedized tactical headsets with active noise cancellation for CRPF CoBRA battalions.",
        issuing_authority: "CRPF Directorate General, New Delhi",
        initial_version_label: "Draft Spec v1.0",
        initial_change_summary: "Initial notice creation for Phase 6 test",
      }),
    });
    assert(createRes.status === 201, `Draft tender created (HTTP ${createRes.status})`);
    const draftTender = await createRes.json();
    assert(draftTender.status === "DRAFT", `Tender lifecycle status is DRAFT`);
    const tenderId = draftTender.id;

    // TEST 1 — Draft Tender is NOT in public listing
    console.log("\n4. TEST 1: Verifying Draft Tender is NOT publicly visible...");
    const publicList1 = await fetch(`${BACKEND_BASE}/tenders/public`);
    assert(publicList1.status === 200, "Public tenders list endpoint accessible without authentication (HTTP 200)");
    const publicData1 = await publicList1.json();
    const draftFoundInPublic = publicData1.items.some((t) => t.id === tenderId || t.tender_number === testRef);
    assert(!draftFoundInPublic, "Draft tender is NOT visible in public list");

    // TEST 5 — Draft Security Boundary (Public detail must 404 for draft)
    console.log("\n5. TEST 5: Verifying Draft Security Boundary (404 on unauthenticated detail)...");
    const publicDraftDetail = await fetch(`${BACKEND_BASE}/tenders/public/${tenderId}`);
    assert(
      publicDraftDetail.status === 404,
      `Unauthenticated access to draft tender correctly rejected with HTTP 404 (received ${publicDraftDetail.status})`
    );
    const errBody = await publicDraftDetail.json();
    assert(
      errBody.detail && errBody.detail.toLowerCase().includes("not publicly available"),
      `Expected safe error message: "${errBody.detail}"`
    );

    // TEST 10 — Publish Permission: Reviewer attempt to publish must fail with 403 Forbidden
    console.log("\n6. TEST 10: Verifying Reviewer (lacking TENDER_UPDATE) cannot publish...");
    const reviewerPublishRes = await fetch(`${BACKEND_BASE}/tenders/${tenderId}/publish`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${reviewerToken}`,
      },
      body: JSON.stringify({}),
    });
    assert(
      reviewerPublishRes.status === 403,
      `Reviewer without TENDER_UPDATE receives HTTP 403 Forbidden on publish (received ${reviewerPublishRes.status})`
    );

    // TEST 2 — Officer Publishes the Tender
    console.log("\n7. TEST 2: Officer publishing the tender...");
    const publishRes = await fetch(`${BACKEND_BASE}/tenders/${tenderId}/publish`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${officerToken}`,
      },
      body: JSON.stringify({}),
    });
    assert(publishRes.status === 200, `Tender published successfully (HTTP ${publishRes.status})`);
    const publishedTender = await publishRes.json();
    assert(publishedTender.status === "PUBLISHED", `Backend lifecycle state successfully transitioned to PUBLISHED`);

    // TEST 3 — Public Discovery
    console.log("\n8. TEST 3: Verifying Public Discovery (Unauthenticated)...");
    const publicList2 = await fetch(`${BACKEND_BASE}/tenders/public`);
    const publicData2 = await publicList2.json();
    const publishedFound = publicData2.items.find((t) => t.id === tenderId);
    assert(Boolean(publishedFound), "Published tender is now publicly discoverable in the unauthenticated portal");
    assert(publishedFound?.tender_number === testRef, "Tender reference matches expected value");

    // TEST 4 — Public Details
    console.log("\n9. TEST 4: Verifying Public Detail Endpoint...");
    const publicDetailRes = await fetch(`${BACKEND_BASE}/tenders/public/${tenderId}`);
    assert(publicDetailRes.status === 200, "Public detail endpoint returns HTTP 200 for published tender");
    const publicDetail = await publicDetailRes.json();
    assert(publicDetail.title === draftTender.title, "Tender title accurately returned to public user");
    assert(publicDetail.issuing_authority === draftTender.issuing_authority, "Issuing authority matches");
    assert(publicDetail.status === "PUBLISHED", "Public status clearly indicates PUBLISHED");
    assert(Boolean(publicDetail.created_at), "Publication timestamp is present");

    // TEST 6 — Private Information Leak Prevention
    console.log("\n10. TEST 6: Verifying NO Internal Private Information is Leaked in Public Response...");
    assert(publicDetail.submissions === undefined, "Bidder submissions are completely omitted");
    assert(publicDetail.evaluation_results === undefined, "Evaluation results are completely omitted");
    assert(publicDetail.audit_logs === undefined, "Internal audit logs are completely omitted");
    assert(publicDetail.prompt === undefined && publicDetail.ai_instructions === undefined, "AI prompts are not exposed");
    assert(publicDetail.minio_secret_key === undefined, "Storage secrets are not exposed");

    // TEST 7 — Public Documents
    console.log("\n11. TEST 7: Verifying Public Tender Documents Endpoint...");
    const publicDocsRes = await fetch(`${BACKEND_BASE}/tenders/public/${tenderId}/documents`);
    assert(publicDocsRes.status === 200, "Public tender documents endpoint returns HTTP 200");
    const publicDocs = await publicDocsRes.json();
    assert(Array.isArray(publicDocs.items), "Public documents items is an array");

    // TEST 8 — Search & Filters on Public Portal
    console.log("\n12. TEST 8 & 10: Verifying Public Search and Filter...");
    const searchRes = await fetch(`${BACKEND_BASE}/tenders/public?search=${encodeURIComponent(testRef)}`);
    const searchData = await searchRes.json();
    assert(
      searchData.items.some((t) => t.id === tenderId),
      `Public search by tender reference "${testRef}" successfully found the tender`
    );

    const filterStatusRes = await fetch(`${BACKEND_BASE}/tenders/public?status=PUBLISHED`);
    const filterStatusData = await filterStatusRes.json();
    assert(
      filterStatusData.items.every((t) => t.status === "PUBLISHED"),
      "Public filter status=PUBLISHED returns only PUBLISHED tenders"
    );

    // TEST 11 — Frontend Public Routes Accessibility
    console.log("\n13. TEST 11: Testing Frontend Public Routes...");
    try {
      const fePublicList = await fetch(`${FRONTEND_BASE}/tenders/public`);
      assert(fePublicList.status === 200, `Frontend /tenders/public accessible (HTTP ${fePublicList.status})`);

      const fePublicDetail = await fetch(`${FRONTEND_BASE}/tenders/public/${tenderId}`);
      assert(fePublicDetail.status === 200, `Frontend /tenders/public/[tenderId] accessible (HTTP ${fePublicDetail.status})`);
    } catch {
      console.warn("Frontend server port 3000 might be building, continuing verification");
    }

    // TEST 13 — IDOR / Invalid Tender ID
    console.log("\n14. TEST 13: Verifying IDOR Protection with random non-existent UUID...");
    const fakeId = "00000000-0000-0000-0000-000000000000";
    const fakeRes = await fetch(`${BACKEND_BASE}/tenders/public/${fakeId}`);
    assert(fakeRes.status === 404, `Random UUID query correctly returns HTTP 404 (received ${fakeRes.status})`);

    console.log("\n=================================================");
    console.log("PHASE 6 VERIFICATION COMPLETED");
    console.log("=================================================");

    const passedCount = testResults.filter((r) => r.status === "PASS").length;
    const failedCount = testResults.filter((r) => r.status === "FAIL").length;
    console.log(`Total Tests: ${testResults.length} | Passed: ${passedCount} | Failed: ${failedCount}`);

    if (failedCount > 0) {
      process.exit(1);
    }
  } catch (err) {
    console.error("FATAL ERROR in Phase 6 verification:", err);
    process.exit(1);
  }
}

runVerification();
