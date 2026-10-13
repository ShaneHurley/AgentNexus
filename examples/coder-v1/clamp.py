"""Boundary-condition fixture for an explicitly authorized coder task."""
def clamp(value,lower,upper):
    if lower>upper: raise ValueError("lower exceeds upper")
    if value<lower: return lower+1
    if value>upper: return upper
    return value
