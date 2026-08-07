"""
Tunable weight tables for the Maintenance Priority Engine.

These are hand-set starting weights, not learned from data -- they encode
domain judgement about which factors matter most. Adjust freely; nothing
elsewhere in the project depends on the exact numbers.
"""

# How structurally serious each defect TYPE is on its own,
# independent of how severe this particular instance looks.
# Cracks are the most safety-critical (can propagate/fracture),
# Shelling next, Discoloration is mostly cosmetic/corrosion-related.
DEFECT_TYPE_WEIGHT = {
    "Cracks-Scratches": 35,
    "Shelling": 30,
    "Discoloration": 10,
}
DEFAULT_DEFECT_WEIGHT = 15  # used if an unseen defect label ever appears

# How severe THIS instance was judged by the K-Means severity module.
SEVERITY_WEIGHT = {
    "Mild": 10,
    "Moderate": 25,
    "Severe": 40,
}
DEFAULT_SEVERITY_WEIGHT = 15

# Historical trend weight: is this wheel's condition getting worse,
# staying flat, or improving across past inspections?
TREND_WEIGHT_WORSENING = 20
TREND_WEIGHT_STABLE = 10
TREND_WEIGHT_IMPROVING = 5
# Used when there's no history yet (new wheel / demo mode) -- neither
# rewards nor penalizes, sits at the stable value.
TREND_WEIGHT_NO_HISTORY = TREND_WEIGHT_STABLE

# Reliability (from the TTA module) scales the whole score down when the
# model itself wasn't confident/stable about the detection -- this is what
# "reduces false alarms" in practice: a LOW-reliability Severe detection
# gets pulled toward a lower risk score instead of triggering an
# immediate-inspection alert on a shaky reading.
RELIABILITY_FACTOR = {
    "HIGH": 1.0,
    "MEDIUM": 0.85,
    "LOW": 0.6,
}
DEFAULT_RELIABILITY_FACTOR = 0.7

# Severity rank used only for trend comparison (worse == higher number).
SEVERITY_RANK = {"Mild": 1, "Moderate": 2, "Severe": 3}

# Risk score cutoffs -> recommended action.
ACTION_THRESHOLDS = [
    (80, "Immediate inspection"),
    (50, "Schedule maintenance"),
    (0, "Monitor only"),
]


def action_for_score(score: float) -> str:
    for threshold, action in ACTION_THRESHOLDS:
        if score >= threshold:
            return action
    return "Monitor only"
