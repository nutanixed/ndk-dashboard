"""
Label filtering utilities
"""

# System label prefixes to filter out
SYSTEM_LABEL_PREFIXES = [
    'kubectl.kubernetes.io/',
    'kubernetes.io/',
    'k8s.io/'
]


def filter_system_labels(labels, strict=False):
    """
    Filter out system labels from a dictionary
    
    Args:
        labels: Dictionary of labels
        strict: If True, filter all system prefixes. If False, only filter kubectl.kubernetes.io
        
    Returns:
        Dictionary with system labels removed
    """
    if not labels:
        return {}
    
    if strict:
        return {
            k: v for k, v in labels.items()
            if not any(k.startswith(prefix) for prefix in SYSTEM_LABEL_PREFIXES)
        }
    else:
        # Only filter kubectl.kubernetes.io (backward compatible)
        return {
            k: v for k, v in labels.items()
            if not k.startswith('kubectl.kubernetes.io/')
        }


def filter_system_label_prefixes(labels):
    """
    Filter out all system label prefixes
    
    Args:
        labels: Dictionary of labels
        
    Returns:
        Dictionary with all system labels removed
    """
    return filter_system_labels(labels, strict=True)


def preserve_system_labels(current_labels, new_labels):
    """
    Merge new labels with existing system labels
    
    Args:
        current_labels: Current label dictionary
        new_labels: New labels to apply
        
    Returns:
        Merged dictionary preserving system labels
    """
    system_labels = {
        k: v for k, v in (current_labels or {}).items()
        if k.startswith('kubectl.kubernetes.io/')
    }
    return {**system_labels, **new_labels}