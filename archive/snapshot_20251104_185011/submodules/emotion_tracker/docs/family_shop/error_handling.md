# Family Shop Error Handling

## Error Code Mapping Table
| Error Code                  | UI Message                                 |
|----------------------------|--------------------------------------------|
| INSUFFICIENT_FUNDS         | Not enough funds in family wallet.         |
| FAMILY_SPENDING_DENIED     | You are not allowed to spend from family.  |
| ITEM_NOT_FOUND             | The selected item could not be found.      |
| REQUEST_NOT_FOUND          | Purchase request not found.                |
| ALREADY_APPROVED           | Request already approved.                  |
| ALREADY_DENIED             | Request already denied.                    |
| SERVER_ERROR               | Something went wrong. Please try again.    |
| ...                        | ...                                        |

## Error Handling Patterns
- All API/service errors are mapped to user-friendly messages
- Providers surface these messages for UI dialogs/snackbars
