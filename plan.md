# Project Modernization Plan: ClipperTV

## Goals

1. Migrate from GCS CSV storage to Supabase database
2. Modernize project structure with proper packaging
3. Eliminate CCRMA server dependency for PDF processing
4. Streamline data flow throughout the application

## Git Branch Plan

main
├── feature/project-structure
│   └── feature/package-setup
├── feature/supabase-integration
│   ├── feature/db-schema-design
│   ├── feature/data-migration
│   └── feature/api-layer
└── feature/pdf-processing
    └── feature/direct-pdf-upload

## Phase 1: Project Structure Modernization

Branch: feature/project-structure

1. Create proper package structure:

```
clippertv/
├── pyproject.toml
├── README.md
├── src/
│   └── clippertv/
│       ├── __init__.py
│       ├── app.py         # Main Streamlit app
│       ├── config.py      # Configuration management
│       ├── data/
│       │   ├── __init__.py
│       │   ├── models.py  # Data models
│       │   ├── store.py   # Data access layer
│       │   └── schema.py  # Database schema
│       ├── pdf/
│       │   ├── __init__.py
│       │   ├── extractor.py   # PDF extraction logic
│       │   └── processor.py   # Processing logic
│       └── viz/
│           ├── __init__.py
│           ├── charts.py      # Chart creation
│           └── dashboard.py   # Dashboard components
└── tests/
    └── ...
```

2. Refactor existing code into the new structure
3. Update dependencies in pyproject.toml
4. Add config management with Pydantic

## Phase 2: Supabase Integration

Branch: feature/supabase-integration

1. Design database schema in Supabase:
  - riders table: rider details
  - trips table: all transit transactions
  - transit_modes table: transit mode details
2. Create data access layer:
  - Implement store.py with Supabase client
  - Create CRUD operations for each entity
  - Add caching for frequent queries
3. Data migration script:
  - Convert existing CSV data to SQL format
  - Upload to Supabase
4. Update visualization components to work with new data format

## Phase 3: Direct PDF Processing

Branch: feature/pdf-processing

1. Eliminate CCRMA server dependency:
  - Process PDFs directly in the app
  - Add direct file upload to Supabase storage
  - Implement serverless function for processing if needed
2. Improve PDF extraction:
  - Enhance the extraction logic
  - Add validation and error handling
  - Create clear separation between extraction and storage
3. Develop a robust PDF processing pipeline:
  - Upload → Extract → Transform → Load to Supabase

## Implementation Timeline

1. Week 1: Project structure modernization
  - Convert to package structure
  - Refactor existing code
  - Set up testing framework
2. Week 2-3: Supabase integration
  - Design and create database schema
  - Implement data access layer
  - Migration script and data transfer
  - Update app to use new data source
3. Week 4: Direct PDF processing
  - Remove CCRMA dependency
  - Implement direct processing
  - Test end-to-end flow
4. Final Week: Testing, documentation, and deployment
  - End-to-end testing
  - Documentation updates
  - Deploy to production
