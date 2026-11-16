# Agent clicks execute at coordinates, never through locator.click()

Every click runs as `page.mouse.click(x, y)` at the target's centre point. Playwright's `locator.click()` refuses a click that an overlay intercepts, which would quietly protect the Unshielded side from click-jacking and make the comparison unfair. The Shielded side instead re-runs the hit-test just before clicking.
