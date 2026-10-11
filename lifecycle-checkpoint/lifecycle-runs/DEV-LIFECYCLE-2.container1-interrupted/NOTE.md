# Interrupted first attempt (previous container)

The previous container started DEV-LIFECYCLE-2 at 2026-10-11 11:51 UTC: review round 1 began and no result was recorded,
then the container was reset. That partial state is kept here unchanged, as history. On 2026-10-11 12:11 UTC the new
container started a fresh run record in `DEV-LIFECYCLE-2/`, using the same config except `integration.authorized = false`.
The driver's rule is that interrupted rounds are not trusted, so this one was not resumed.
