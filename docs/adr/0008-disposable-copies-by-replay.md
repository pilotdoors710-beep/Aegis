# Disposable copies rebuild the checkout by replaying Actions

Trials and the Two-view check reproduce the real checkout in fresh browser contexts by replaying the Agent's executed Actions from the start URL, then verify the copy matches before testing. Copying `storage_state` would not reproduce DOM, JavaScript or server state, and general browser cloning is out of scope. Copies are restricted to the arena origin and always closed. Any mismatch or timeout is reported as unavailable.
