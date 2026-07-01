# SE Demo Guide: Feature Flags + Predictive Test Selection

**Audience:** Existing or prospective CloudBees customers
**Duration:** 20–30 minutes (live demo portion ~12 minutes)
**Pre-requisite:** At least 20 observation builds completed in CBCI

---

## The Story You're Telling

> "Feature flags let you release code safely. Smart Tests lets you test that code efficiently. Together, they mean your CI only runs the tests that actually matter for the change you just made."

Three sentences. That's the pitch. Everything else is proof.

---

## Pre-Demo Checklist

Before the call, confirm:

- [ ] CBCI pipeline has 20+ successful builds on `main` with `SMART_TESTS_OBSERVATION = true`
- [ ] Unify Smart Tests shows a confidence curve (not flat at zero) for `todo-backend-tests`
- [ ] A test build with `SMART_TESTS_OBSERVATION = false` has run and shows subset selection
- [ ] ArgoCD QA sync is green
- [ ] You have CBCI open in one tab, Unify in another

If observation builds are not done: demo can still work in observation mode — show the data accumulating and explain what will happen once confidence is built. Be explicit: "we're still in observation mode here, but this is what subsetting looks like once the model is trained."

---

## Demo Flow (Three Acts)

---

### Act 1 — The Setup (3 min)

**What to show:** The CBCI pipeline parameters screen

**Navigate to:**
`CBCI → two-tier-app → todo-backend-pipeline → main → Build with Parameters`

**Say:**
> "Here's the pipeline for our todo backend. Notice these parameters at the top — these are our feature flags. Enhanced stats, due date warnings, bulk operations. And this last one — Smart Tests observation mode."

> "In a real customer environment, these flags would be controlled by CloudBees Feature Management — real-time delivery, targeting rules, gradual rollout. Here we're using environment variables to show you the pattern without any SDK dependency. The swap is one method call."

**Point to the four booleans. Then say:**
> "The observation switch is what makes this interesting. When it's on, we run every test so Smart Tests can learn. When it's off, Smart Tests decides which tests to run. Let me show you what that looks like."

---

### Act 2 — The Data (5 min)

**What to show:** Unify Smart Tests — test session list and confidence curve

**Navigate to:**
`Unify → Smart Tests → Test Suite: todo-backend-tests`

**Show the session list. Say:**
> "Each row here is one CI build. You can see the test suite, how many tests ran, pass/fail. Notice these early builds all say 'observation mode' — that's Smart Tests learning which tests are sensitive to which code."

**Click into a recent session. Say:**
> "This is a typical observation run — 35 tests, all passed. Nothing surprising. But what Smart Tests is doing behind the scenes is building a model: for every commit, it's asking 'which files changed?' and 'which tests caught regressions?' Over 20+ builds, it maps code paths to test coverage."

**Navigate to the confidence curve (if visible). Say:**
> "This curve is the key metric. As we run more builds, Smart Tests gets more confident about what to skip. Once we cross the confidence threshold — we've set it at 90% — subsetting kicks in automatically."

---

### Act 3 — The Payoff (5 min)

**What to show:** A subsetting build — either already run, or trigger one live

**Option A — Show an existing subset build:**

Navigate to a build where `SMART_TESTS_OBSERVATION = false`. Click into the console output, find the Test stage. Say:

> "This build had observation mode turned off. We made a change to the bulk operations endpoint — literally three lines of code behind the `FEATURE_BULK_OPERATIONS` flag. Watch what Smart Tests did."

Find the line: `Smart Tests selected X of 35 tests:` and read it aloud:

> "Five tests. Out of thirty-five. Smart Tests looked at what changed — the bulk complete route — found the tests that cover that code path, and skipped the other thirty. The build finished in under a minute instead of three."

> "And critically — if those five tests pass, Smart Tests is telling us with 90% confidence that the other thirty would have passed too. That's not skipping tests randomly. That's surgical precision."

**Option B — Trigger live (dramatic but risky if network is slow):**

1. Click "Build with Parameters"
2. Set `SMART_TESTS_OBSERVATION = false`, `FEATURE_BULK_OPERATIONS = true`
3. Start build, switch to Console Output
4. Point to the subset selection lines as they appear

---

### Closing (2 min)

**Say:**
> "Let me put a number on this. This app has 35 tests. A typical enterprise app has thousands. If Smart Tests can skip 85% of your suite on flag-gated PRs — and that's a conservative estimate based on how flags segment code — your CI compute bill drops by that same amount for those builds. More importantly, your developers get feedback in seconds, not minutes."

> "And because this is all driven by actual execution data — not static analysis, not code ownership guesses — it gets more accurate over time, not less."

**If they ask about CloudBees Feature Management specifically:**
> "The flags in this demo are environment variables — simple, portable. The code is designed so that replacing the env-var check with a CloudBees FM SDK call is one method. You get real-time flag delivery, per-user targeting, gradual rollout percentages, and a full audit log. Smart Tests doesn't care how the flag is delivered — it only cares about which code ran during which test."

---

## Adapting for Specific Customer Contexts

| Customer situation | Angle to emphasize |
|---|---|
| Large test suite (1000+ tests) | "Your CI time compresses as Smart Tests learns — most customers see 60–80% reduction on flag-gated PRs" |
| Slow pipelines / long feedback loops | "Smart Tests is surgical — developers stop waiting for tests that can't possibly fail" |
| Already using feature flags | "You already have the flag boundaries. Smart Tests just needs to observe a few cycles to map them to tests. No code changes." |
| Not using feature flags yet | "Feature flags give you safe releases. Smart Tests makes the CI cost of those safer releases go down, not up." |
| Concerned about test confidence | "Show them the confidence curve — 90% threshold means Smart Tests won't subset until it's statistically confident. You set the threshold, not us." |
| Kubernetes / GKE environment | "The agent pod spins up fresh each build — same as your environment. Java, Python, Docker, all clean." |

---

## Common Questions

**Q: What if Smart Tests skips a test that would have caught a bug?**
> The confidence threshold prevents this. At 90%, Smart Tests has seen enough builds to know with high probability which tests are unaffected. And for any build where there's uncertainty — new code, no prior data — it defaults to running everything. The model is conservative by design.

**Q: Does Smart Tests work with frameworks other than pytest?**
> Yes — JUnit, TestNG, Maven, Gradle, Cypress, Jest, and more. The `record tests` command takes standard JUnit XML output, which every major framework produces.

**Q: How long does the observation period take?**
> Typically 20–30 builds. For teams that build multiple times per day, that's a few days. For weekly release teams, a few weeks. The confidence curve in Unify shows you exactly where you are.

**Q: What happens to the flag-to-test mapping when we refactor?**
> Smart Tests rebuilds the mapping continuously. Every build is a new data point. If you rename a function, the next build that touches it re-maps it. The model degrades gracefully and recovers within a few builds.

**Q: Can we run this in parallel with our existing CI?**
> Yes. Observation mode is additive — you add four CLI commands to your existing pipeline. Tests still run exactly as before. No risk, no disruption. Subsetting is opt-in.

---

## Reference Links

- GitHub repo: `https://github.com/tdesai2705/unify-ref-todo-backend`
- CBCI pipeline: `http://cloudbees-ci.34.75.0.106.nip.io/two-tier-app/job/todo-backend-pipeline/`
- Unify: `https://cloudbees.io` (workspace: PS Lab / tejas)
- ArgoCD: `http://todo-app.34.75.0.106.nip.io` (QA), `http://todo-app-prod.34.75.0.106.nip.io` (prod)

---

*Maintained by PS Lab. Questions: tdesai@cloudbees.com*
