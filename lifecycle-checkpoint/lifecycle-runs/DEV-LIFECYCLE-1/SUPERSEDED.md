This state directory (rounds R1-R5, repairs P1-P4, driver pinned at 12ac37a then d5fccdf) is kept unchanged as
evidence. On 2026-10-11T02:13Z the repaired driver fbac437 refused to resume it: its stricter verify() (repair of
R2-01) requires resume_to to be bound in stage events, which the older driver did not write. That is a format change
between driver versions, not tampering, but the driver's rule is to start a fresh state directory rather than trust
or rewrite evidence. The review continues in ../DEV-LIFECYCLE-1b on candidate fbac437 with fresh reviewer processes.
