/**
 * End-to-End Verification Suite for PHASE 7:
 * BIDDER REGISTRATION + BIDDER PORTAL + STRICT DATA ISOLATION
 */

const BACKEND_BASE = "http://127.0.0.1:8000/api/v1";

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

async function runSuite() {
  console.log("=================================================");
  console.log("STARTING PHASE 7 BIDDER PORTAL VERIFICATION");
  console.log("=================================================");

  const timestamp = Date.now().toString().slice(-6);
  const emailA = `bidder_a_${timestamp}@apexdefence.co.in`;
  const emailB = `bidder_b_${timestamp}@zenithballistics.co.in`;
  const password = "SecureBidderPassword123!";

  let tokenA = "";
  let tokenB = "";
  let bidderAId = "";
  let bidderBId = "";
  let applicationAId = "";
  let applicationBId = "";
  let publishedTenderId = "";

  try {
    // -------------------------------------------------------------
    // TEST A — Bidder Registration (Valid)
    // -------------------------------------------------------------
    console.log("\n[TEST A] Bidder Registration (Valid Bidder A)");
    const regResA = await fetch(`${BACKEND_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailA,
        password: password,
        full_name: "Vikram Malhotra",
        company_name: "Apex Defense Systems Private Limited",
        phone: "+91 9811223344",
      }),
    });
    assert(regResA.status === 201, `Bidder A registration succeeded (HTTP ${regResA.status})`);
    const regDataA = await regResA.json();
    tokenA = regDataA.access_token;
    assert(Boolean(tokenA), "Received valid JWT access token upon registration");

    // Verify /auth/me for Bidder A
    const meResA = await fetch(`${BACKEND_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(meResA.status === 200, "Authenticated /auth/me returns HTTP 200");
    const meDataA = await meResA.json();
    bidderAId = meDataA.id;
    assert(meDataA.email === emailA, "Email matches registered address");
    assert(meDataA.company_name === "Apex Defense Systems Private Limited", "Company name correctly mapped");
    assert(meDataA.roles.includes("BIDDER"), "Assigned role strictly matches 'BIDDER'");
    assert(!meDataA.roles.includes("PROCUREMENT_OFFICER"), "Bidder does NOT possess PROCUREMENT_OFFICER role");
    assert(!meDataA.roles.includes("ADMIN"), "Bidder does NOT possess ADMIN role");

    // -------------------------------------------------------------
    // TEST B — Invalid Registration & Duplicate Prevention
    // -------------------------------------------------------------
    console.log("\n[TEST B] Invalid Registration & Duplicate Account Rejection");
    // 1. Duplicate email registration
    const dupRes = await fetch(`${BACKEND_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailA, // same email
        password: password,
        full_name: "Another Representative",
        company_name: "Duplicate Firm Ltd",
      }),
    });
    assert(dupRes.status === 409, `Duplicate corporate email rejected with HTTP 409 Conflict (received ${dupRes.status})`);
    const dupBody = await dupRes.json();
    assert(dupBody.detail.includes("already exists"), `Safe duplicate error message: "${dupBody.detail}"`);

    // 2. Short password validation (<8 chars)
    const shortPwdRes = await fetch(`${BACKEND_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: `short_pwd_${timestamp}@test.com`,
        password: "short",
        full_name: "Test User",
        company_name: "Test Corp",
      }),
    });
    assert(shortPwdRes.status === 422, `Weak password rejected with HTTP 422 Unprocessable Content (received ${shortPwdRes.status})`);

    // -------------------------------------------------------------
    // TEST C — Bidder Login
    // -------------------------------------------------------------
    console.log("\n[TEST C] Bidder Login with Valid Credentials");
    const loginResA = await fetch(`${BACKEND_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: emailA, password: password }),
    });
    assert(loginResA.status === 200, `Login succeeded with HTTP 200`);
    const loginDataA = await loginResA.json();
    assert(Boolean(loginDataA.access_token), "Login response returns valid JWT bearer token");

    // -------------------------------------------------------------
    // TEST D — Wrong Credentials Rejection
    // -------------------------------------------------------------
    console.log("\n[TEST D] Wrong Password Rejection");
    const wrongPwdRes = await fetch(`${BACKEND_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: emailA, password: "IncorrectPassword999!" }),
    });
    assert(wrongPwdRes.status === 401, `Invalid credentials rejected with HTTP 401 Unauthorized (received ${wrongPwdRes.status})`);

    // -------------------------------------------------------------
    // Register Bidder B for Cross-User Isolation Tests
    // -------------------------------------------------------------
    console.log("\n[*] Registering Bidder B for Multi-Bidder Isolation Verification");
    const regResB = await fetch(`${BACKEND_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailB,
        password: password,
        full_name: "Suresh Patil",
        company_name: "Zenith Ballistics Private Limited",
        phone: "+91 9988776655",
      }),
    });
    assert(regResB.status === 201, "Bidder B registration succeeded");
    tokenB = (await regResB.json()).access_token;
    bidderBId = (await (await fetch(`${BACKEND_BASE}/auth/me`, { headers: { Authorization: `Bearer ${tokenB}` } })).json()).id;

    // -------------------------------------------------------------
    // TEST E — Public Tender → Apply Flow
    // -------------------------------------------------------------
    console.log("\n[TEST E] Public Tender → Apply Flow");
    // Find an open published tender
    const publicTendersRes = await fetch(`${BACKEND_BASE}/tenders/public`);
    const publicTenders = await publicTendersRes.json();
    assert(publicTenders.items.length > 0, `Found ${publicTenders.items.length} open published tenders`);
    const targetTender = publicTenders.items[0];
    publishedTenderId = targetTender.id;

    // 1. Unauthenticated attempt to apply must fail with 401
    const unauthApply = await fetch(`${BACKEND_BASE}/bidder/apply/${publishedTenderId}`, {
      method: "POST",
    });
    assert(unauthApply.status === 401, `Unauthenticated application attempt correctly rejected with HTTP 401 (received ${unauthApply.status})`);

    // 2. Bidder A applies for tender
    const applyResA = await fetch(`${BACKEND_BASE}/bidder/apply/${publishedTenderId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(applyResA.status === 201, `Bidder A applied for tender successfully (HTTP ${applyResA.status})`);
    const appDataA = await applyResA.json();
    applicationAId = appDataA.id;
    assert(Boolean(applicationAId), "Generated unique application submission UUID");
    assert(appDataA.status === "DRAFT" || appDataA.status === "RECEIVED", `Application status is initialized to 'DRAFT' or 'RECEIVED' (got ${appDataA.status})`);
    assert(appDataA.tender_id === publishedTenderId, "Application correctly bound to published tender ID");

    // 3. Bidder B applies for tender
    const applyResB = await fetch(`${BACKEND_BASE}/bidder/apply/${publishedTenderId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    assert(applyResB.status === 201, `Bidder B applied for tender successfully (HTTP ${applyResB.status})`);
    const appDataB = await applyResB.json();
    applicationBId = appDataB.id;
    assert(applicationAId !== applicationBId, "Each bidder receives an independent, isolated submission ID");

    // -------------------------------------------------------------
    // TEST F — Bidder Dashboard Real Data
    // -------------------------------------------------------------
    console.log("\n[TEST F] Bidder Dashboard Real Data Aggregation");
    const dashResA = await fetch(`${BACKEND_BASE}/bidder/dashboard`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(dashResA.status === 200, "Bidder A dashboard retrieved (HTTP 200)");
    const dashDataA = await dashResA.json();
    assert(dashDataA.company_name === "Apex Defense Systems Private Limited", "Dashboard displays company name");
    assert(dashDataA.total_applications === 1, `Real application count matches DB (1)`);
    assert(dashDataA.received_count === 1, `Received count is 1`);
    assert(dashDataA.available_tenders_count >= 1, `Available tenders count >= 1`);
    assert(dashDataA.recent_applications.length === 1, "Recent applications list has 1 item");
    assert(dashDataA.recent_applications[0].id === applicationAId, "Recent application matches Bidder A application ID");

    // -------------------------------------------------------------
    // TEST G — My Applications List (Strict Isolation)
    // -------------------------------------------------------------
    console.log("\n[TEST G] My Applications Listing & Isolation");
    const listResA = await fetch(`${BACKEND_BASE}/bidder/applications`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(listResA.status === 200, "Bidder A applications retrieved");
    const listDataA = await listResA.json();
    assert(listDataA.total === 1, "Bidder A has exactly 1 application");
    assert(listDataA.items[0].id === applicationAId, "Bidder A application ID verified");

    const listResB = await fetch(`${BACKEND_BASE}/bidder/applications`, {
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    assert(listResB.status === 200, "Bidder B applications retrieved");
    const listDataB = await listResB.json();
    assert(listDataB.total === 1, "Bidder B has exactly 1 application");
    assert(listDataB.items[0].id === applicationBId, "Bidder B application ID verified");
    // Ensure Bidder A does not see Bidder B's application in the list
    const crossLeakA = listDataA.items.some((i) => i.id === applicationBId);
    const crossLeakB = listDataB.items.some((i) => i.id === applicationAId);
    assert(!crossLeakA && !crossLeakB, "ZERO cross-bidder leakage in applications list");

    // -------------------------------------------------------------
    // TEST H — IDOR Attack Prevention
    // -------------------------------------------------------------
    console.log("\n[TEST H] IDOR Attack Prevention (Bidder B querying Bidder A)");
    const idorRes = await fetch(`${BACKEND_BASE}/bidder/applications/${applicationAId}`, {
      headers: { Authorization: `Bearer ${tokenB}` }, // Bidder B token attempting to access Bidder A's application
    });
    assert(
      idorRes.status === 404,
      `IDOR attack strictly blocked: Bidder B receives HTTP 404 when querying Bidder A's application (received ${idorRes.status})`
    );
    const idorBody = await idorRes.json();
    assert(
      idorBody.detail.includes("not found or access denied"),
      `Expected safe error detail: "${idorBody.detail}"`
    );

    // Verify Bidder A CAN access their own application
    const ownRes = await fetch(`${BACKEND_BASE}/bidder/applications/${applicationAId}`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(ownRes.status === 200, "Bidder A successfully accesses their own application (HTTP 200)");
    const ownData = await ownRes.json();
    assert(ownData.id === applicationAId, "Application ID matches");
    assert(ownData.tender_id === publishedTenderId, "Tender ID matches");
    assert(Array.isArray(ownData.criteria_checklist), "Criteria checklist is present as array");

    // -------------------------------------------------------------
    // TEST I — Officer / Bidder Role Isolation
    // -------------------------------------------------------------
    console.log("\n[TEST I] Officer / Bidder Privilege Boundary Enforcement");
    // Bidder attempting to access admin-test endpoint
    const adminTestRes = await fetch(`${BACKEND_BASE}/auth/admin-test`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(
      adminTestRes.status === 403,
      `Bidder blocked from admin-test with HTTP 403 Forbidden (received ${adminTestRes.status})`
    );

    // Bidder attempting to create a tender (officer permission required)
    const createTenderRes = await fetch(`${BACKEND_BASE}/tenders`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenA}`,
      },
      body: JSON.stringify({
        tender_number: "CRPF/HACK/2026/001",
        title: "Unauthorized Tender Creation Attempt",
      }),
    });
    assert(
      createTenderRes.status === 403,
      `Bidder blocked from creating tenders with HTTP 403 Forbidden (received ${createTenderRes.status})`
    );

    // -------------------------------------------------------------
    // TEST J — Closed / Draft Tender Application Protection
    // -------------------------------------------------------------
    console.log("\n[TEST J] Closed / Draft Tender Application Rejection");
    // Login as officer to create a draft tender
    const officerLoginRes = await fetch(`${BACKEND_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "officer@crpf.gov.in", password: "OfficerPassword123!" }),
    });
    const officerToken = (await officerLoginRes.json()).access_token;

    const draftTenderRes = await fetch(`${BACKEND_BASE}/tenders`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${officerToken}`,
      },
      body: JSON.stringify({
        tender_number: `CRPF/DRAFT-P7/${timestamp}`,
        title: "Confidential Draft Tender Not Yet Published",
        description: "Testing application block on draft tender",
        issuing_authority: "CRPF Directorate General",
        initial_version_label: "v1.0-draft",
        initial_change_summary: "Draft creation for verification",
      }),
    });
    const draftTender = await draftTenderRes.json();

    // Bidder attempting to apply to DRAFT tender
    const applyDraftRes = await fetch(`${BACKEND_BASE}/bidder/apply/${draftTender.id}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(
      applyDraftRes.status === 400,
      `Attempt to apply to DRAFT tender rejected with HTTP 400 (received ${applyDraftRes.status})`
    );
    const draftErr = await applyDraftRes.json();
    assert(draftErr.detail.includes("Only PUBLISHED tenders accept applications"), `Safe error: "${draftErr.detail}"`);

    // -------------------------------------------------------------
    // TEST K — Bidder Profile Update
    // -------------------------------------------------------------
    console.log("\n[TEST K] Bidder Profile Read & Update");
    const profileResA = await fetch(`${BACKEND_BASE}/bidder/profile`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    assert(profileResA.status === 200, "Bidder A profile retrieved (HTTP 200)");
    const profileDataA = await profileResA.json();
    assert(profileDataA.email === emailA, "Profile email matches");
    assert(profileDataA.active_applications_count === 1, "Active applications count matches 1");

    // Update profile
    const updateResA = await fetch(`${BACKEND_BASE}/bidder/profile`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokenA}`,
      },
      body: JSON.stringify({
        company_name: "Apex Defense Systems Global Pvt Ltd",
        phone: "+91 9999988888",
      }),
    });
    assert(updateResA.status === 200, "Profile updated successfully (HTTP 200)");
    const updatedDataA = await updateResA.json();
    assert(updatedDataA.company_name === "Apex Defense Systems Global Pvt Ltd", "Company name successfully updated");
    assert(updatedDataA.phone === "+91 9999988888", "Contact phone successfully updated");
    assert(updatedDataA.email === emailA, "Email remains immutable");

    console.log("\n=================================================");
    console.log("PHASE 7 VERIFICATION COMPLETE");
    console.log("=================================================");
    const passed = testResults.filter((r) => r.status === "PASS").length;
    const failed = testResults.filter((r) => r.status === "FAIL").length;
    console.log(`Total Tests: ${testResults.length} | Passed: ${passed} | Failed: ${failed}`);

    if (failed > 0) {
      process.exit(1);
    }
  } catch (err) {
    console.error("FATAL ERROR in Phase 7 verification:", err);
    process.exit(1);
  }
}

runSuite();
