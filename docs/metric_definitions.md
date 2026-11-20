# Metric definitions and assumptions

| Metric | Definition |
|---|---|
| Orders | Count of unique `order_id` after cleaning |
| Gross revenue | Sum of `order_value` for all orders, returned or not |
| Net revenue | Gross revenue minus the value of returned orders |
| Average order value (AOV) | Gross revenue divided by orders |
| Return rate | Returned orders divided by all orders |
| Change | Relative change: (this week minus last week) divided by last week. For return rate this is the relative change of the rate, not percentage points |
| Daily anomaly | A day whose revenue has an absolute z-score of 2 or more against the daily revenue of the whole input period |

## Periods

- **This week** is the latest 7 days in the data, ending on the most recent order date.
- **Last week** is the 7 days before that.

## Cleaning rules

1. Duplicate `order_id` rows are dropped (first kept).
2. Rows with an unreadable date or a non-numeric order value are dropped.
3. Rows with a negative order value are dropped.
4. `returned` is true when the value is 1, true, yes or y (case-insensitive).

## Assumptions and limits

- A return is counted in the week of the order, not the week of the return.
- The anomaly test uses the whole input period, so one very large spike also raises the average and standard deviation. With short histories, treat flags as a prompt to check, not as a finding.
- Revenue is in the currency of the input file. No currency conversion is done.
- Sample data in this repository is synthetic.
