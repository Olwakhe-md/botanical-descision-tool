Data Cleaning & Quality Assessment

Project: Botanical Decision Support Tool (BDST)

Overview

The focus was on cleaning, standardizing, and validating a real-world botanical dataset (≈18,000 plant records) sourced from Plants For A Future (PFAF).
The goal was to ensure the data is structurally sound, semantically consistent, and honest about uncertainty before any exploratory analysis or modeling.

No imputation or feature engineering was performed at this stage.

Dataset

Source: Plants For A Future (PFAF)

Records: ~18,000 plant species

Domain: Botany, edible plants, medicinal plants, cultivation information

Key Identifier: scientific_name

Key Objectives (Week 2)

Enforce a reliable entity identifier

Standardize column names and text formats

Remove noise and reference artifacts

Diagnose redundancy across text-heavy columns

Accurately characterize missing data without forcing completeness

Cleaning & Standardization Performed
1. Schema & Column Standardization

Normalized column names (lowercase, underscores)

Clarified ambiguous column semantics through renaming

Removed duplicate or redundant columns identified via automated diagnostics

2. Reference & Noise Removal

Removed citation-style references (e.g. [1], [2, 3]) from all text columns

Standardized placeholder values ("nan", "unknown", empty strings) into true missing values (NaN)

3. Identifier Enforcement

Treated scientific_name as the unique entity key

Rows missing scientific_name were removed to preserve data integrity

latin_name_search was used only as a backfill check, not as a primary identifier

4. Redundancy & Similarity Diagnostics

Instead of merging columns based on intuition, quantitative diagnostics were applied:

Cultivation vs Care Requirements

Coverage analysis showed nested but not redundant structure

Median Jaccard similarity ≈ 0.03

Decision: Keep both columns (distinct, complementary information)

Plant Use Columns

Columns analyzed:

other_uses

special_uses

edible_uses

Findings:

Median Jaccard similarity across pairs ≤ 0.12

Low lexical overlap despite similar naming

Decision: Keep all three columns

Summary Column

Contains valuable high-level information

High missingness (~59%) reflects optional documentation, not data error

Decision: Keep without imputation

5. Missingness Analysis (Final)

After enforcing identifier integrity and normalizing fake-missing values:

Column	Missing Fraction
summary	~58%
special_uses	~42%
common_names_merged	~11%
Core identifiers & ratings	0%

Interpretation:

Missingness is structured and domain-consistent

High missingness appears only in optional descriptive fields

Core decision signals and identifiers are complete

No imputation was performed.

Key Decisions

Preserve uncertainty instead of forcing completeness

Retain semantically distinct text fields even when names appear similar

Delay feature engineering and inference to later stages

Outputs

Cleaned dataset saved as:
pfaf_plants_clean_week2.csv

Fully documented cleaning and diagnostic notebook:
01_week2_data_cleaning.ipynb