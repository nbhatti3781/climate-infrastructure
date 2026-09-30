def annualized_exposed_length(frequency: float, exposed_road_length: float) -> float:
    """AAEL = annualized frequency × exposed road length."""
    if frequency < 0 or exposed_road_length < 0:
        raise ValueError("Frequency and length must be non-negative")
    return frequency * exposed_road_length


def annualized_relative_exposure(aael: float, total_road_length: float) -> float:
    """Annualized relative road exposure = AAEL ÷ total road length."""
    if aael < 0:
        raise ValueError("AAEL must be non-negative")
    if total_road_length <= 0:
        raise ValueError("Total road length must be positive")
    return aael / total_road_length


def min_max_normalize(value: float, minimum: float, maximum: float) -> float:
    """Scale a value to 0–1 using the stated dashboard method."""
    if maximum <= minimum:
        raise ValueError("Maximum must be greater than minimum")
    return (value - minimum) / (maximum - minimum)


def weighted_aadt(aadt_and_lengths: list[tuple[float, float]]) -> float:
    """Length-weighted AADT across exposed road pieces."""
    total_length = sum(length for _, length in aadt_and_lengths)
    if total_length <= 0:
        return 0.0
    return sum(aadt * length for aadt, length in aadt_and_lengths) / total_length


def percentile_rank(rank: float, count: int) -> float:
    """Convert a 1-based average rank to the dashboard's 0–1 score."""
    if count <= 1:
        return 0.0
    return (rank - 1) / (count - 1)


def transportation_stress(frequency: float, exposure: float, consequence: float) -> float:
    """Final score = normalized frequency × exposure × consequence."""
    values = (frequency, exposure, consequence)
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("All Transportation Stress components must be within 0–1")
    return frequency * exposure * consequence
