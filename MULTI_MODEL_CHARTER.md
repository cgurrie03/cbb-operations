# Three-model comparison, version 1 — November 2, 2026

Question: which of three fixed model structures best predicts future D1-vs-D1 men's college basketball margin, total points including overtime, and home winner?

One row is one ESPN game. Inputs are the existing point-in-time opponent-adjusted efficiency margin, efficiency total, expected pace, and venue indicator. No betting line or same-game outcome is a feature. Historical ratings must satisfy rating_cutoff <= decision_time and latest_result_used <= rating_cutoff; runtime prior results retain the existing 24-hour release delay.

Structures: standardized Ridge regression / logistic regression; histogram gradient-boosted regressors / classifier; ExtraTrees regressors / classifier. Fixed parameters, no tuning on evaluation seasons. All three use identical complete-case rows and training-only preprocessing. Baselines: training mean / home-win prevalence and raw efficiency margin / total. The old frozen paper experiment stays separate.

Historical evaluation is expanding-season walk-forward for seasons 2023–2026, training strictly on earlier seasons with a 24-hour boundary embargo. These seasons have been examined in prior project work, so results are historical research, not new blind evidence. Freeze the deployed model fits through 2026; no 2027 outcomes enter fitted parameters.

Primary metrics: margin MAE, total MAE, and winner log loss (lower is better). Secondary metrics: RMSE, winner Brier and accuracy. Every model and the equal-weight ensemble are scored on the same games. Do not select a universal winner from unlike metrics. Do not infer calibrated spread/total confidence or profitable betting from point estimates.

Main projection: arithmetic mean of the three margins, totals, and home-win probabilities. Model disagreement is descriptive, not a confidence interval. Do not select the largest claimed confidence; probability calibration must be comparable before such a policy can be considered.

Forward comparison: start at actual deployment, save immutable timestamped forecasts with version/hash and matchup identity inside 24 hours of tipoff and before tipoff minus 60 minutes. Canonical record is the latest qualifying snapshot per game, chosen using timestamps alone. Retain every snapshot privately. Grade only source-confirmed final scores, once per game, on the intersection with all three predictions. Already completed games have no reconstructed forecasts. Show pending counts and unavailable metrics explicitly. Formal model promotion requires at least 200 matched forward finals and evidence across multiple periods; averaging remains the fixed display policy until a new version is explicitly chosen.

Acceptance: all chronology, unique-key, complete-case, feature-only prediction, artifact-hash and future-snapshot checks pass. Missing input or a model failure means unavailable, never a silently reduced two-model average. Outcomes may update grades, never the saved predictions. Required artifacts: fitted model bundle, source hashes, fold metrics, manifest, timestamped forward ledger, public per-game comparison and performance table.
