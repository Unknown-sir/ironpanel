# IronPanel 19.8.9

- Node install command now includes the active panel port in `--master`.
- Raw IP/localhost master URLs on non-443 panel ports default to HTTP instead of broken HTTPS.
- Nodes can be edited or deleted from the Nodes page.
- Deleting a node clears dependent user assignments, sessions, port rows, routing maps and queued jobs.
