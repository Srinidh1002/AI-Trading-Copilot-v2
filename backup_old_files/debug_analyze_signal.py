# Add this at the end of the file, before the class closing brace
# This is a debug patch to log all signals
def _debug_analyze_signal(self, tick_data):
    """Debug wrapper for analyze_signal"""
    result = self._original_analyze_signal(tick_data)
    if result:
        logger.info(f"[SIGNAL DEBUG] {result}")
    return result
