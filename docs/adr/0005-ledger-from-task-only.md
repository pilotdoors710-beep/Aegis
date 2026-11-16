# The Ledger is parsed from the task alone and frozen for the Run

One LLM call turns only the user's task text into the Ledger before browsing. Page content never reaches it, and the model is frozen. Permission flags default to false. An authorized extra must be named explicitly; a flag alone never permits an unnamed extra. Changing permissions means starting a new Run. A page that could edit the Ledger could authorize its own Trap.
