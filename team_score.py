"""Point forecasts for team scores, with season maturity and linear tails."""
import numpy as np

INPUTS = ['eff_margin', 'eff_total', 'expected_pace', 'venue_effect', 'min_history']


def design(frame):
    margin, total, pace, venue, games = frame[INPUTS].to_numpy(dtype=float).T
    sign = np.where(margin >= 0, 1, -1)
    gap = abs(margin)
    early = np.exp(-games / 5)
    return np.column_stack([
        gap, np.maximum(gap - 12, 0), np.maximum(gap - 24, 0),
        total, pace, venue * sign, early, early * gap,
        early * (total - 140), early * (pace - 69),
    ]), sign


def predict(frame, spec):
    x, sign = design(frame)

    def linear(name):
        model = spec[name]
        return x @ np.asarray(model['weights']).T + model['intercept']

    if spec['method'] == 'robust':
        return np.column_stack([np.zeros(len(x)),linear('total')])
    if spec['method'] == 'possession':
        scores = linear('efficiency') * linear('possessions')[:, None] / 100
    else:
        scores = linear('scores')
    return np.column_stack([(scores[:, 0] - scores[:, 1]) * sign, scores.sum(axis=1)])


def total_offset(residuals, ages_days):
    """Estimate a shrunk league-wide scoring shift from available finals."""
    ages = np.asarray(ages_days)
    eligible = (ages >= 1) & (ages <= 14)
    weights = np.exp2(-ages[eligible] / 7)
    return float(np.clip(weights @ np.asarray(residuals)[eligible] / (100 + weights.sum()), -5, 5))
