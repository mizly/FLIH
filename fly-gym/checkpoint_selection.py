"""Select weights for a new connectome training run."""
from pathlib import Path
import re


def resolve_resume_checkpoint(setting, checkpoint_dir, final_checkpoint):
    """None starts fresh; 'latest' selects the newest saved weights by mtime.

    Include the final snapshot because it can contain updates made after the
    last completed iteration (for example after a clean interruption).
    """
    if setting is None:
        return None
    if setting != "latest":
        path = Path(setting)
        if not path.is_file():
            raise FileNotFoundError(f"Requested checkpoint does not exist: {path}")
        return str(path)
    candidates = [
        path for path in Path(checkpoint_dir).glob("connectome_rnn_dagger_iter_*.pt")
        if path.is_file() and re.fullmatch(r"connectome_rnn_dagger_iter_\d+\.pt", path.name)
    ]
    final = Path(final_checkpoint)
    if final.is_file():
        candidates.append(final)
    if not candidates:
        return None
    return str(max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name)))
