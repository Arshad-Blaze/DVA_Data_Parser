# Retailer HEB

Record-based file (HDR/U/TRL record types), fixed-width.

Tests: the RecordBasedParser auto-detects record types, builds an internal
record tree (Store parent → Detail children, Trailer as boundary), and flattens
automatically — with no UI record-type or flatten decisions.

- HDR: header (store, date) — parent
- U: UPC detail record — child
- TRL: trailer — transaction boundary, excluded from detail rows