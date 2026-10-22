This module adds an tier review board with form, tree, kanban, calendar,
pivot, graph and search views.

It also limits which tier reviews a user finds: a review is only returned
when the user can read its document, or when the user takes part in it
(reviewer, requester or the one who did it). Without this, any internal
user can list every review, with its document name, of documents they
cannot open.
