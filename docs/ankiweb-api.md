# AnkiWeb `/svc/*` Endpoint Reference

Reverse-engineered from the minified protobuf client. Message names match the
reference spec [`ankiweb-svc.reference.proto`](./ankiweb-svc.reference.proto).

**Transport notes**

- `POST` endpoints send a protobuf body (`Content-Type: application/octet-stream`).
- `GET` endpoints (`item-info`, `list-decks`, `list-addons`) carry the request in
  URL query parameters — there is **no** protobuf request message; only the
  response is protobuf.
- `{}` means an empty message (no fields).

**Sliced status** — the last column shows whether a compilable per-endpoint
`.proto` has been sliced yet under `proto/ankiweb/**`. Slice on demand.

______________________________________________________________________

## Account — authentication & account settings

| Method | URL                                | Purpose                                                              | Request                          | Response                     | Sliced                |
| ------ | ---------------------------------- | -------------------------------------------------------------------- | -------------------------------- | ---------------------------- | --------------------- |
| POST   | `/svc/account/get-account-status`  | Check whether the user is logged in; return flag + optional redirect | `GetAccountStatusRequest` `{}`   | `GetAccountStatusResponse`   | —                     |
| POST   | `/svc/account/login`               | Log in with username/password, issue session token                   | `LoginRequest`                   | `LoginResponse`              | `account/login.proto` |
| POST   | `/svc/account/check-terms`         | Ask whether the terms of use still need confirming                   | `CheckTermsRequest` `{}`         | `CheckTermsResponse`         | —                     |
| POST   | `/svc/account/confirm-terms`       | Confirm agreement to the terms of use                                | `ConfirmTermsRequest`            | `ConfirmTermsResponse` `{}`  | —                     |
| POST   | `/svc/account/get-settings`        | Fetch current account settings (email)                               | `GetSettingsRequest` `{}`        | `GetSettingsResponse`        | —                     |
| POST   | `/svc/account/update-settings`     | Change password **or** email                                         | `UpdateSettingsRequest`          | `UpdateSettingsResponse`     | —                     |
| POST   | `/svc/account/total-media`         | Get total media size in bytes                                        | `TotalMediaRequest` `{}`         | `TotalMediaResponse`         | —                     |
| POST   | `/svc/account/remove-account`      | Delete the account (requires current password)                       | `RemoveAccountRequest`           | `RemoveAccountResponse`      | —                     |
| POST   | `/svc/account/signup`              | Register a new account                                               | `SignupRequest`                  | `SignupResponse`             | —                     |
| POST   | `/svc/account/verify-email`        | Verify email by token / track send status                            | `VerifyEmailRequest`             | `VerifyEmailResponse`        | —                     |
| POST   | `/svc/account/resend-verification` | Re-send the verification email                                       | `ResendVerificationRequest` `{}` | `ResendVerificationResponse` | —                     |
| POST   | `/svc/account/reset-password`      | Reset flow: send email → check token → set new password              | `ResetPasswordRequest`           | `ResetPasswordResponse`      | —                     |

## Decks — deck management & publishing

| Method | URL                           | Purpose                                               | Request                      | Response                  | Sliced |
| ------ | ----------------------------- | ----------------------------------------------------- | ---------------------------- | ------------------------- | ------ |
| POST   | `/svc/decks/deck-list-info`   | Deck tree with counts and collection/media sizes      | `DeckListInfoRequest`        | `DeckListInfoResponse`    | —      |
| POST   | `/svc/decks/create-deck`      | Create a deck                                         | `CreateDeckRequest`          | `CreateDeckResponse` `{}` | —      |
| POST   | `/svc/decks/rename-deck`      | Rename a deck                                         | `RenameDeckRequest`          | `RenameDeckResponse`      | —      |
| POST   | `/svc/decks/remove-deck`      | Delete a deck                                         | `RemoveDeckRequest`          | `RemoveDeckResponse` `{}` | —      |
| POST   | `/svc/decks/select-deck`      | Set the current (active) deck                         | `SelectDeckRequest`          | `SelectDeckResponse` `{}` | —      |
| POST   | `/svc/decks/deck-share-info`  | Metadata for the deck-publishing form                 | `DeckShareInfoRequest`       | `DeckShareInfoResponse`   | —      |
| POST   | `/svc/decks/deck-share`       | Publish (share) a deck                                | `DeckShareRequest`           | `DeckShareResponse` `{}`  | —      |
| POST   | `/svc/decks/deck-share-state` | Poll the publishing state (WAITING / IN_PROGRESS / …) | `DeckShareStateRequest` `{}` | `DeckShareStateResponse`  | —      |

## Study — the review loop

| Method | URL                            | Purpose                                                 | Request                     | Response                        | Sliced |
| ------ | ------------------------------ | ------------------------------------------------------- | --------------------------- | ------------------------------- | ------ |
| POST   | `/svc/study/study-cards`       | Fetch the card queue and/or submit an answer for a card | `StudyCardsRequest`         | `StudyCardsResponse`            | —      |
| POST   | `/svc/study/upgrade-scheduler` | Upgrade to the v3 scheduler                             | `UpgradeSchedulerRequest`   | `UpgradeSchedulerResponse` `{}` | —      |
| POST   | `/svc/study/get-deck-limits`   | Get daily new/review limits                             | `GetDeckLimitsRequest` `{}` | `GetDeckLimitsResponse`         | —      |
| POST   | `/svc/study/set-deck-limits`   | Set daily limits                                        | `SetDeckLimitsRequest`      | `SetDeckLimitsResponse` `{}`    | —      |

## Editor — creating & editing notes

| Method | URL                               | Purpose                                                     | Request                        | Response                    | Sliced                             |
| ------ | --------------------------------- | ----------------------------------------------------------- | ------------------------------ | --------------------------- | ---------------------------------- |
| POST   | `/svc/editor/add-or-update`       | Add a new note (AddMode) or edit an existing one (EditMode) | `AddOrUpdateRequest`           | `AddOrUpdateResponse` `{}`  | `editor/add_or_update.proto`       |
| POST   | `/svc/editor/get-note-info`       | Get a note's contents for editing                           | `GetNoteInfoRequest`           | `GetNoteInfoResponse`       | —                                  |
| POST   | `/svc/editor/get-info-for-adding` | Form data for adding: notetypes, decks, fields              | `GetInfoForAddingRequest` `{}` | `GetInfoForAddingResponse`  | `editor/get_info_for_adding.proto` |
| POST   | `/svc/editor/get-notetype-fields` | Get the fields of a specific notetype                       | `GetNotetypeFieldsRequest`     | `GetNotetypeFieldsResponse` | `editor/get_notetype_fields.proto` |

## Search

| Method | URL                  | Purpose                            | Request         | Response              | Sliced |
| ------ | -------------------- | ---------------------------------- | --------------- | --------------------- | ------ |
| POST   | `/svc/search/search` | Search notes/cards by query string | `SearchRequest` | `SearchCardsResponse` | —      |

## Shared — shared-item catalog, reviews & add-ons

| Method  | URL                            | Purpose                                                   | Request                  | Response                       | Sliced |
| ------- | ------------------------------ | --------------------------------------------------------- | ------------------------ | ------------------------------ | ------ |
| **GET** | `/svc/shared/item-info`        | Detailed info about a shared item (deck/add-on) + reviews | *query params*           | `SharedItemInfoResponse`       | —      |
| POST    | `/svc/shared/remove-item`      | Remove one of your shared items                           | `RemoveItemRequest`      | `RemoveItemResponse` `{}`      | —      |
| POST    | `/svc/shared/get-own-review`   | Get your own review of an item                            | `GetOwnReviewRequest`    | `GetOwnReviewResponse`         | —      |
| POST    | `/svc/shared/set-own-review`   | Post/update your review (thumbs + text)                   | `SetOwnReviewRequest`    | `SetOwnReviewResponse` `{}`    | —      |
| POST    | `/svc/shared/report-copyright` | Report a copyright violation                              | `ReportCopyrightRequest` | `ReportCopyrightResponse` `{}` | —      |
| POST    | `/svc/shared/items-by-author`  | Other items by the same author                            | `ItemsByAuthorRequest`   | `ItemsByAuthorResponse`        | —      |
| **GET** | `/svc/shared/list-decks`       | Catalog of shared decks (list/search)                     | *query params*           | `ListDecksResponse`            | —      |
| **GET** | `/svc/shared/list-addons`      | Catalog of shared add-ons                                 | *query params*           | `ListAddonsResponse`           | —      |
| POST    | `/svc/shared/list-mine`        | Your shared items and their reviews                       | `ListMineRequest` `{}`   | `ListMineResponse`             | —      |
| POST    | `/svc/shared/reply-to-review`  | Reply to a review as the item's author                    | `ReplyToReviewRequest`   | `ReplyToReviewResponse` `{}`   | —      |
| POST    | `/svc/shared/get-addon-info`   | Add-on info for upload/update                             | `GetAddonInfoRequest`    | `GetAddonInfoResponse`         | —      |
| POST    | `/svc/shared/upload-addon`     | Upload/update an add-on (zip + version branches)          | `UploadAddonRequest`     | `UploadAddonResponse`          | —      |

______________________________________________________________________

## Notes for building a client (e.g. ankibot)

- The card-adding path is the chain
  `account/login` → `editor/get-info-for-adding` → `editor/get-notetype-fields` → `editor/add-or-update`.
  Resolve the notetype by name from `get-info-for-adding`, never from its `current_notetype_id`:
  an `add-or-update` makes its notetype current, so that field follows whatever was added last.
- Requests go over binary protobuf, so only field **numbers** and **types** reach
  the wire — field names in the `.proto` can be renamed freely.
- `.proto` files are the contract of an external system.
