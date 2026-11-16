# The Agent view is built in one place and excludes detector-only facts

`agent.build_agent_view` is the only code that decides what the Agent sees. Detector-only fields (opacity, visibility, contrast, occlusion, bbox, downloads, onclick) never reach the Agent on either Side, so both Sides see what a typical DOM agent sees. Only Sanitizing differs, and that is part of the shield. Leaking those fields would give the Unshielded baseline defenses it would not normally have.
