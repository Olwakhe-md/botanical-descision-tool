 Exploratory Data Analysis (EDA) 

Project: Botanical Decision Support Tool (BDST)

Overview

This notebook focuses on Exploratory Data Analysis (EDA) of a cleaned botanical dataset derived from Plants For A Future (PFAF).
The goal of this stage is to understand:

+ how medicinal and edible properties are distributed,

+ how these properties relate to each other,

+ where safety (hazard) information appears,

+ and what these patterns imply for a responsible decision-support system.

All analysis is descriptive and evidence-aware. 


Dataset Context

~18,000 plant species after cleaning

Each plant identified by a scientific name

Key attributes analyzed:

Edibility rating (ordinal, 0–5)

Medicinal rating (ordinal, 0–5)

Known hazards (textual descriptions)

Botanical family

Key EDA Questions:

+ Are edibility and medicinal usefulness related?

+ Do patterns change when viewed at the family level?

+ How does hazard documentation relate to edibility and medicinal ratings?

+ What does this imply for BDST design?

1. Edibility vs Medicinal Rating
Observation

A scatter plot of edibility rating vs medicinal rating shows no strong linear relationship. Plants span all combinations:

edible but weakly medicinal,

strongly medicinal but non-edible,

both high,

both low.

Interpretation

Edibility and medicinal usefulness are largely independent dimensions.
This supports treating them as separate signals in the BDST rather than collapsing them into a single score.

2. Family-Level Analysis
Approach

Family counts were computed to understand dataset composition.

Family-level average edibility and medicinal ratings were calculated.

To avoid over-interpreting small families, analysis was restricted to families with ≥20 species.

Findings

Large families (e.g. Asteraceae, Rosaceae, Lamiaceae) dominate the dataset.

Family-level averages still show no strong edibility–medicinal correlation, mirroring species-level results.

This suggests that the independence of these properties persists across taxonomic groupings.

Implication

Family membership provides context, not deterministic rules.
BDST recommendations should avoid family-level generalizations without supporting evidence.

3. Hazard Analysis (Key Safety Insight)
Hazard Definition

The known_hazards column is fully populated and often contains statements such as “none known”.
Therefore, hazard presence was defined conservatively as the presence of explicit warning language (e.g. “toxic”, “poisonous”, “irritant”), rather than non-null values.

absence of hazard warnings is not  proof of safety

hazard documentation reflects both risk and degree of human interaction

3.1 Hazard vs Medicinal Rating

Finding
Plants with higher medicinal ratings tend to show a higher proportion of documented hazards.

Interpretation
Medicinal potency often correlates with:

bioactive compounds,

stronger physiological effects,

and therefore greater need for caution.

This reinforces the idea that medicinal usefulness and safety must be evaluated separately.

3.2 Hazard vs Edibility Rating

Finding
Hazard documentation is relatively high at both extremes:

low edibility plants (often intrinsically toxic),

high edibility plants (widely used, hence well-documented).

Interpretation
This produces a non-linear (often U-shaped) pattern:

non-edible plants → hazards due to toxicity,

highly edible plants → hazards due to preparation, overuse, contraindications, or special populations.

Key Insight

Edibility does not imply safety, and non-edibility does not imply absence of documentation.

4. Implications for BDST v1

From EDA, several design principles emerge:

Treat edibility, medicinal usefulness, and hazard presence as distinct dimensions

Surface explicit hazard warnings as cautionary signals

The BDST v1 should support exploration and risk awareness

Outputs:

Fully documented EDA notebook:

Species-level patterns

Family-level trends

Hazard overlays and interpretations

Clear analytical foundation for BDST v1 logic

