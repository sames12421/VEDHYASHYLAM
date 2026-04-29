# 🌿 NAMASTE ↔ ICD-11 TM2 Mapper
### Standardized AYUSH Diagnosis Integration for Indian EMR Systems

> A mapping system bridging NAMASTE and WHO ICD-11 TM2 codes for standardized AYUSH diagnosis documentation, integrated into EMRs in compliance with India's EHR Standards.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Objectives](#objectives)
- [System Architecture](#system-architecture)
- [Flowchart](#flowchart)
- [Modules](#modules)
- [Data Standards](#data-standards)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [API Reference](#api-reference)
- [Compliance](#compliance)
- [Contributing](#contributing)
- [License](#license)

---

## 🔍 Overview

India's AYUSH healthcare system — encompassing **Ayurveda**, **Yoga & Naturopathy**, **Unani**, **Siddha**, and **Homeopathy** — serves millions of patients daily. Yet the digital infrastructure for documenting traditional medicine diagnoses remains fragmented and globally disconnected.

This project builds a **unified code-mapping and EMR integration layer** that:

- Maps **NAMASTE portal codes** (India's national AYUSH morbidity standard) to **WHO ICD-11 TM2 codes** (global traditional medicine classification)
- Exposes a RESTful API for EMR systems to query, validate, and record AYUSH diagnoses
- Ensures full compliance with **EHR Standards for India** (MoHFW)

---

## ❗ Problem Statement

| Layer | Problem |
|---|---|
| **Clinical Documentation** | EMRs lack standardized AYUSH diagnosis terminology |
| **National Coding** | NAMASTE codes exist but are not integrated into EMR workflows |
| **Global Interoperability** | ICD-11 TM2 exists but is not mapped to NAMASTE |
| **EHR Compliance** | No unified system meets India's MoHFW EHR Standards for AYUSH |

The **absence of a cross-mapping system** between NAMASTE and ICD-11 TM2 creates data silos, hinders national health reporting, and prevents India's traditional medicine data from participating in global health intelligence.

---

## 🎯 Objectives

1. **Build a NAMASTE ↔ ICD-11 TM2 bidirectional code mapping database**
2. **Develop an API layer** for EMR systems to access mapped codes in real time
3. **Create an EMR integration module** compatible with India's EHR Standards
4. **Enable morbidity reporting** to national (NHP/AYUSH Ministry) and global (WHO) systems
5. **Provide a clinician-facing search interface** for AYUSH practitioners

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLINICIAN / EMR INTERFACE                │
│              (Web Portal / HMIS / Hospital EMR System)          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ FHIR R4 / REST API
┌──────────────────────────▼──────────────────────────────────────┐
│                     API GATEWAY LAYER                           │
│         Authentication │ Rate Limiting │ Audit Logging          │
└──────────┬─────────────────────────────────┬────────────────────┘
           │                                 │
┌──────────▼──────────┐           ┌──────────▼──────────────────┐
│   NAMASTE MODULE    │           │     ICD-11 TM2 MODULE       │
│  Code Search        │           │  WHO API Integration        │
│  Validation         │           │  TM2 Code Lookup            │
│  Morbidity Tags     │           │  Description Mapping        │
└──────────┬──────────┘           └──────────┬────────────────────┘
           │                                 │
┌──────────▼─────────────────────────────────▼────────────────────┐
│                    MAPPING ENGINE CORE                          │
│                                                                 │
│   NAMASTE Code ──► Concept Normalization ──► ICD-11 TM2 Code   │
│   ICD-11 TM2   ──► Reverse Lookup        ──► NAMASTE Code      │
│                                                                 │
│   Confidence Score │ Mapping Type │ Version Control            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                     MAPPING DATABASE                            │
│   PostgreSQL + JSONB │ NAMASTE Codes │ ICD-11 TM2 Codes        │
│   Crosswalk Tables   │ Audit Trails  │ Version History          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                   REPORTING & EXPORT LAYER                      │
│   NHP Dashboard │ AYUSH Ministry Reports │ WHO Global Reporting │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flowchart

```
                    ┌──────────────────────┐
                    │  AYUSH Practitioner  │
                    │  Records Diagnosis   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Enter Diagnosis in  │
                    │    EMR / Portal      │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Search NAMASTE Code │◄──── NAMASTE Portal DB
                    │  (by keyword/system) │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  NAMASTE Code Found? │
                    └──────┬──────┬────────┘
                          YES     NO
                           │       │
                           │  ┌────▼──────────────┐
                           │  │ Flag for Manual   │
                           │  │ Review / Custom   │
                           │  │ Code Request      │
                           │  └───────────────────┘
                           │
              ┌────────────▼────────────────┐
              │  Mapping Engine Triggered   │
              │  NAMASTE Code → Lookup      │
              └────────────┬────────────────┘
                           │
              ┌────────────▼────────────────┐
              │  ICD-11 TM2 Equivalent      │◄──── WHO ICD-11 API
              │  Code Retrieved             │
              └────────────┬────────────────┘
                           │
              ┌────────────▼────────────────┐
              │  Mapping Confidence Check   │
              └────┬───────────────┬────────┘
                   │               │
              HIGH/EXACT        PARTIAL/LOW
                   │               │
                   │  ┌────────────▼──────────┐
                   │  │  Flag for Clinician   │
                   │  │  Confirmation         │
                   │  └────────────┬──────────┘
                   │               │
              ┌────▼───────────────▼──────────┐
              │  Record in EMR with Both Codes │
              │  NAMASTE Code + ICD-11 TM2     │
              └────────────┬───────────────────┘
                           │
              ┌────────────▼────────────────┐
              │  EHR Standards Validation   │◄──── MoHFW EHR Rules
              │  (MoHFW Compliance Check)   │
              └────────────┬────────────────┘
                           │
              ┌────────────▼────────────────┐
              │   Save to Patient Record    │
              └────────────┬────────────────┘
                           │
              ┌────────────▼────────────────┐
              │  Aggregate Morbidity Data   │
              └────┬───────────────┬────────┘
                   │               │
       ┌───────────▼───┐   ┌───────▼──────────────┐
       │  AYUSH/NHP    │   │  WHO Global TM        │
       │  National     │   │  Reporting (ICD-11)   │
       │  Dashboard    │   └──────────────────────┘
       └───────────────┘
```

---

## 🧩 Modules

### 1. `namaste-connector`
Interfaces with the NAMASTE portal to fetch, cache, and search AYUSH diagnosis codes.

- Supports all AYUSH systems: Ayurveda, Siddha, Unani, Yoga, Homeopathy
- Full-text search across disease names, synonyms, and classical terms
- Periodic sync with NAMASTE portal updates

### 2. `icd11-tm2-connector`
Integrates with the WHO ICD-11 API to retrieve TM2 module codes.

- Queries WHO's official ICD-11 linearization API
- Parses TM2-specific chapters (Ayurveda conditions, Chinese medicine, etc.)
- Maintains a local cache for offline/low-connectivity EMR environments

### 3. `mapping-engine`
Core logic for bidirectional NAMASTE ↔ ICD-11 TM2 code mapping.

- **Exact Match**: Direct 1:1 code equivalents
- **Partial Match**: Conceptually related codes with confidence scoring
- **Unmapped**: Flagged for expert clinical review
- Mapping versioning and audit trails

### 4. `emr-integration-api`
RESTful API layer for hospital EMR and HMIS systems.

- FHIR R4 compatible endpoints
- Supports HL7 messaging
- Role-based access control (RBAC) for practitioners, admins, and auditors

### 5. `compliance-validator`
Validates all records against India's EHR Standards (MoHFW).

- Checks mandatory fields, code formats, and data types
- Generates compliance reports
- Flags non-conforming entries for correction

### 6. `reporting-dashboard`
Web-based dashboard for morbidity analytics.

- State/district-level AYUSH disease burden visualization
- Export to AYUSH Ministry reporting formats
- WHO-compatible XML/JSON exports

---

## 📐 Data Standards

| Standard | Purpose | Reference |
|---|---|---|
| **NAMASTE Codes** | National AYUSH morbidity classification | Ministry of AYUSH, GoI |
| **ICD-11 TM2** | Global traditional medicine classification | WHO ICD-11 (2022+) |
| **EHR Standards for India** | EMR compliance framework | MoHFW, 2016 (updated) |
| **FHIR R4** | Health data interoperability | HL7 International |
| **SNOMED CT** | Clinical terminology (optional mapping layer) | SNOMED International |
| **ABDM** | Ayushman Bharat Digital Mission compliance | NHA, GoI |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python (FastAPI) |
| **Database** | PostgreSQL + JSONB |
| **Caching** | Redis |
| **API Standard** | REST + FHIR R4 |
| **Frontend** | React.js (Clinician Portal) |
| **Auth** | OAuth 2.0 + JWT |
| **Containerization** | Docker + Docker Compose |
| **CI/CD** | GitHub Actions |
| **Documentation** | Swagger / OpenAPI 3.0 |

---

## ⚙️ Installation

```bash
# Clone the repository
git clone https://github.com/your-org/namaste-icd11-mapper.git
cd namaste-icd11-mapper

# Set up environment variables
cp .env.example .env
# Edit .env with your NAMASTE API key and WHO ICD-11 credentials

# Start with Docker Compose
docker-compose up --build

# The API will be available at:
# http://localhost:8000/api/v1

# Swagger docs at:
# http://localhost:8000/docs
```

---

## 📡 API Reference

### Search NAMASTE Code
```http
GET /api/v1/namaste/search?q={diagnosis_term}&system={ayurveda|siddha|unani}
```

### Get ICD-11 TM2 Mapping
```http
GET /api/v1/map/namaste-to-icd11?code={NAMASTE_CODE}
```

### Reverse Lookup
```http
GET /api/v1/map/icd11-to-namaste?code={ICD11_TM2_CODE}
```

### Validate EMR Record
```http
POST /api/v1/validate/ehr
Content-Type: application/json

{
  "patient_id": "ABHA-XXXX",
  "namaste_code": "AYU-001-XX",
  "icd11_tm2_code": "TM1.XX.XX",
  "practitioner_id": "REG-XXXX",
  "date": "2025-01-01"
}
```

---

## ✅ Compliance

This system is designed to comply with:

- 📋 **EHR Standards for India** — Ministry of Health & Family Welfare (MoHFW)
- 🏥 **ABDM Health Data Management Policy** — National Health Authority
- 🌍 **WHO ICD-11 Implementation Guidelines**
- 🔒 **Digital Personal Data Protection Act, 2023 (DPDPA)** — India
- 📊 **AYUSH Morbidity Reporting Framework** — Ministry of AYUSH

---

## 🤝 Contributing

Contributions are welcome from clinicians, informaticians, and developers.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m 'Add your feature'`
4. Push to branch: `git push origin feature/your-feature`
5. Open a Pull Request

For AYUSH terminology contributions or mapping corrections, please open an issue with the label `mapping-review` and include clinical references.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- **Ministry of AYUSH, Government of India** — NAMASTE Portal
- **World Health Organization** — ICD-11 TM2 Module
- **Ministry of Health & Family Welfare** — EHR Standards for India
- **National Health Authority** — ABDM Framework

---

<p align="center">Built to bridge traditional wisdom with modern digital health infrastructure 🌿</p>
