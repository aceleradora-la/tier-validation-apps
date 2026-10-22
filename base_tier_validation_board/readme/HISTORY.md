## 18.0.1.0.0

- Migration to 18.0, from OCA/server-ux#1155.
- Reviews stay visible to the users who take part in them (reviewer,
  requester, done by) even if they cannot read the document.
- Pagination: the access filter runs on the whole domain and `offset` /
  `limit` are applied once. Before, from the second page on the list came
  out empty.
- Reviews of a model that is not installed any more are hidden instead of
  raising an error.
- Removed the `_read_group_raw` override: it does not exist since 17.0 and
  `_read_group` goes through `_search`.
