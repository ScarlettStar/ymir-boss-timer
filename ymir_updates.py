"""Policy shared by download completion and the automatic installation loop."""


def can_auto_install(bosses, now, idle_since):
    return now - idle_since >= 120 and not any(b.get("end", 0) > now for b in bosses)
