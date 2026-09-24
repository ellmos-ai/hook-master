# Third-Party Licenses & Transparency Notice (Level 1 SBOM)

> **Project:** `ellmos-ai/hook-master`<br>
> **Audited:** 2026-09-24<br>
> **Repository License:** [MIT License](LICENSE)<br>
> **Canonical Notice:** [NOTICE](NOTICE)<br>
> **Architecture & Privacy:** 100% Local-First, Zero-Egress, Unprivileged User-Mode (`RunAsInvoker`), Fail-Closed Consent Gate

---

## Executive Summary & Compliance Assurance

`hook-master` is engineered under strict architectural and governance invariants: **100% Local-First, Zero-Egress by default, unprivileged user-mode execution (`RunAsInvoker`), pointer-only registry design, and fail-closed consent verification**. All hook registry pointer entries, one-way materialization steps (`deploy`/`diff`/`status`), consent allowlist checks, and doctor integrity diagnostics operate entirely within local process and local filesystem boundaries.

All direct, optional, and development dependencies utilized across `hook-master` are distributed under strictly **permissive open-source licenses** (MIT, Apache-2.0, PSFL-2.0). There are **zero AGPL or restrictive copyleft constraints**, ensuring maximum portability for multi-agent setups, personal developer machines, enterprise infrastructure, and automated multi-agent deployments.

Furthermore, `hook-master` guarantees:
1. **100% Local-First & Zero Egress (INV-LOCAL-01):** Operates entirely on the local filesystem (`~/.hook-master/registry.json`, `~/.hook-master/allowlist.json`). Zero network telemetry, zero phone-home calls, and zero external network requests.
2. **Unprivileged User-Mode (`RunAsInvoker` / INV-SEC-02):** Executes safely in standard unprivileged user space without requiring root or administrator elevation.
3. **Pointer-Only Registry Architecture (INV-PTR-03):** The registry stores metadata and filesystem pointers to canonical script files; it never embeds executable script code inside `registry.json`.
4. **Executable Code Trust Class Separation (INV-EXEC-04):** Recognizes executable hooks as a distinct trust class from static text policies; hashes are verified on every check and drift is never silently resolved.
5. **One-Way Materialization Invariant (INV-MAT-05):** Always copies canonical source to deploy target (`canonical -> deployed`), never the reverse. Direct changes to deployed targets are reported as drift, not automatically overwritten back to canonical.
6. **Fail-Closed Consent Allowlist (INV-CONSENT-06):** Newly registered hook scripts require explicit user consent via `allowlist.json` before materialization; unconsented scripts are blocked fail-closed.
7. **Comprehensive Hook-Doctor Diagnostics (INV-DOC-07):** Deep diagnostic checks verify canonical file existence, SHA-256 hash match, syntax compilation (`py_compile`), mtime drift, and agent config JSON/TOML syntax integrity.
8. **Optional Transport Independence (INV-TRANS-08):** Standalone operation requires zero external packages; `system_gap_master` adapter operates purely as an optional, graceful transport layer.
9. **100% Permissive Audited Dependency Stack (INV-LIC-09):** Clean MIT/PSFL stack audited in this document, zero copyleft or AGPL contamination.
10. **Dual Security Response & Triage SLA (INV-SLA-10):** Commitments to 48-hour response confirmation and 5-day triage via canonical security channels (`security@open-bricks.org`, `security@ellmos.ai`).

---

## Level 1 SBOM Invariant Cross-Reference Matrix

| Invariant Code | Core Requirement | Implementation Mechanism | License / Dependency Impact | Compliance Status |
|:---|:---|:---|:---|:---:|
| `INV-LOCAL-01` | 100% Local-First & Zero-Egress | Python Standard Library (`pathlib`, `json`, `hashlib`) | Zero external runtime network dependencies | **PASS (100% Offline)** |
| `INV-SEC-02` | Unprivileged User Execution | Operates under standard OS user token (`RunAsInvoker`) | Zero root or administrator elevation requirements | **PASS (User-Mode)** |
| `INV-PTR-03` | Pointer-Only Registry Architecture | Metadata pointer storage (`registry.json`, `allowlist.json`) | Rejects embedded executable script bodies | **PASS (Pointer-Only)** |
| `INV-EXEC-04` | Executable Trust Class Separation | Cryptographic SHA-256 integrity verification | Distinguishes executable hooks from static policies | **PASS (Cryptographic)** |
| `INV-MAT-05` | One-Way Materialization Invariant | Deterministic copy (`canonical -> deployed`) | Never overwrites canonical source from target | **PASS (One-Way)** |
| `INV-CONSENT-06` | Fail-Closed Consent Allowlist | Explicit user consent gate (`allowlist.json`) | Unconsented hooks blocked from deployment | **PASS (Fail-Closed)** |
| `INV-DOC-07` | Comprehensive Hook-Doctor Engine | AST/bytecode validation (`py_compile`), drift & config checks | Standard library diagnostics with zero external tools | **PASS (Self-Contained)** |
| `INV-TRANS-08` | Optional Transport Independence | Decoupled adapter architecture (`adapters/system_gap.py`) | Zero runtime dependency on optional transport | **PASS (Decoupled)** |
| `INV-LIC-09` | 100% Permissive Dependency Footprint | MIT & PSFL-2.0 audited dependency stack | Zero copyleft, GPL, or AGPL contamination | **PASS (Permissive)** |
| `INV-SLA-10` | 48h Security SLA & Coordinated Disclosure | Binding 48h response & 5d triage commitment | Coordinated disclosure via security@open-bricks.org | **PASS (Contractual)** |

---

## Runtime Dependency Matrix

| Package | Role / Functional Scope | License | Project Repository / Upstream |
|:---|:---|:---|:---|
| **Python Standard Library** | Core CLI runner, file operations, hashlib (SHA-256), json, logging, path manipulation, py_compile, shutil | [PSFL-2.0](https://docs.python.org/3/license.html) | [python/cpython](https://github.com/python/cpython) |

*Note:* `hook-master` has **zero external runtime dependencies** (`dependencies = []` in `pyproject.toml`). It runs out-of-the-box on standard Python 3.10+ runtimes.

---

## Optional & Sibling Adapter Integration

| Package | Role / Functional Scope | License | Project Repository / Upstream |
|:---|:---|:---|:---|
| **system-gap-master** (optional adapter) | Cross-machine transfer yard sync view export adapter (`adapters/system_gap.py`) | [MIT](https://github.com/ellmos-ai/system-gap-master/blob/main/LICENSE) | [ellmos-ai/system-gap-master](https://github.com/ellmos-ai/system-gap-master) |
| **policy-registry** (architectural sibling) | Architectural reference for pointer-only registry design (zero runtime coupling) | [MIT](https://github.com/ellmos-ai/policy-registry/blob/main/LICENSE) | [ellmos-ai/policy-registry](https://github.com/ellmos-ai/policy-registry) |

---

## Development, Testing & Quality Assurance Tooling

| Package | Usage & Purpose | License | Source / Upstream |
|:---|:---|:---|:---|
| **pytest** | Automated test runner, contract verification suites, mock fixtures | [MIT](https://github.com/pytest-dev/pytest/blob/main/LICENSE) | [pytest-dev/pytest](https://github.com/pytest-dev/pytest) |
| **jsonschema** | Module manifest schema contract validation against `ellmos.module.v2.schema.json` | [MIT](https://github.com/python-jsonschema/jsonschema/blob/main/LICENSE) | [python-jsonschema/jsonschema](https://github.com/python-jsonschema/jsonschema) |
| **ruff** | Fast Python linter and code formatting enforcement | [MIT / Apache-2.0](https://github.com/astral-sh/ruff/blob/main/LICENSE-MIT) | [astral-sh/ruff](https://github.com/astral-sh/ruff) |
| **setuptools** | Standard package build backend (PEP 517 / PEP 621 compliant) | [MIT](https://github.com/pypa/setuptools/blob/main/LICENSE) | [pypa/setuptools](https://github.com/pypa/setuptools) |

---

## Full License Texts (Excerpts & Notices)

### 1. Python Software Foundation License Version 2 (PSFL-2.0)
Python standard library modules are used under the PSF License Agreement.  
Copyright (c) 2001-2026 Python Software Foundation. All rights reserved.

### 2. MIT License (MIT)
Used by `hook-master`, `system-gap-master`, `policy-registry`, `pytest`, `jsonschema`, and `setuptools`.

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:  
>  
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.  
>  
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### 3. Apache License Version 2.0 (Apache-2.0)
Co-licensed by `ruff`.

> Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:  
> http://www.apache.org/licenses/LICENSE-2.0  
> Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
