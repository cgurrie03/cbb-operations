# Evaluation charter

Compare direct team-score regression and possession/efficiency regression on identical D1 games. Train on seasons ending before each 2023â€“2026 test season. Use the existing reconstructed forecast cutoffs and 24-hour results embargo. Regularization and feature definitions are fixed before scoring. The existing three-model equal-weight ensemble is the control. Use margin and total MAE separately, with signed favorite and total bias and November results as diagnostics. A target can be promoted if pooled MAE improves, improvement occurs in at least three folds, and November MAE does not materially deteriorate (0.15 points). Use the 2026 opening-week results as an already-inspected stress test only. Archive prospective paired forecasts before the existing one-hour cutoff and score subsequent finals at the same game grain. Market-line performance requires timestamped lines and a separate evaluation.

Follow-up candidate, specified after the first replay. Fit the direct team-score model with a two-season half-life for training weights and apply the same promotion gate. The reused folds remain development evidence.

Second follow-up totals candidate. Apply a league-wide correction to the frozen ensemble total using only eligible prior final-score residuals from the same season. Use a seven-day half-life, a 14-day lookback, 100 pseudo-games at zero bias, and cap the change at five points. Historical validation applies the correction separately at each reconstructed cutoff with a 24-hour embargo.

Third follow-up totals candidate. Fit a standardized Huber regression directly to final total using the same team-score features (epsilon 1.35). This tests whether reducing the leverage of extreme scores better serves MAE.
