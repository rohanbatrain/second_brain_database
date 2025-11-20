# Progress Bar Visibility Fix

## Problem
When utilization percentage was very small (e.g., 0.01% or 0.1%), the progress bar was invisible because:
1. The width was calculated as `0.01%` which is less than 1 pixel
2. No minimum width was set, so the bar didn't render

## Solution

### 1. Added `getProgressBarWidth()` Helper Function

```typescript
export function getProgressBarWidth(percentage: number): number {
  // Ensure percentage is valid
  if (!isFinite(percentage) || percentage < 0) {
    return 0;
  }
  
  // Cap at 100%
  if (percentage > 100) {
    return 100;
  }
  
  // For very small percentages (< 1%), show at least 1% so the bar is visible
  // This ensures users can see there's some allocation even if it's tiny
  if (percentage > 0 && percentage < 1) {
    return 1;
  }
  
  return percentage;
}
```

### 2. Updated Progress Bar Rendering

**Before:**
```tsx
<div className="h-4 bg-muted rounded-full overflow-hidden">
  <div
    className="h-full bg-green-500"
    style={{ width: `${Math.min(utilizationPercentage, 100)}%` }}
  />
</div>
```

**After:**
```tsx
<div className="h-4 bg-muted rounded-full overflow-hidden">
  <div
    className="h-full bg-green-500"
    style={{ 
      width: `${getProgressBarWidth(utilizationPercentage)}%`,
      minWidth: utilizationPercentage > 0 ? '2px' : '0'
    }}
  />
</div>
```

## Behavior Examples

| Actual % | Display Text | Bar Width | Visual Result |
|----------|--------------|-----------|---------------|
| 0%       | "0%"         | 0%        | Empty bar (no color) |
| 0.01%    | "0.01%"      | 1%        | Tiny visible bar (2px min) |
| 0.5%     | "0.5%"       | 1%        | Small visible bar (2px min) |
| 1%       | "1%"         | 1%        | Small visible bar |
| 50%      | "50%"        | 50%       | Half-filled bar |
| 100%     | "100%"       | 100%      | Full bar |

## Benefits

1. **Visual Feedback**: Users can now see when there's ANY allocation, even if it's 0.01%
2. **Accurate Text**: The percentage text still shows the accurate decimal value (e.g., "0.01%")
3. **Consistent UX**: All progress bars across the app behave the same way
4. **Accessibility**: The 2px minimum width ensures the bar is visible on all screen sizes

## Technical Details

### Why 1% minimum for the width calculation?
- Below 1%, the CSS percentage width becomes less than 1 pixel on most screens
- Setting it to 1% ensures at least ~10-15 pixels on a typical progress bar

### Why 2px minWidth?
- Even 1% can be invisible on very small containers
- 2px is the minimum visible width on retina displays
- Only applies when percentage > 0, so empty bars stay empty

### Decimal Precision
The `formatPercentage()` function still shows accurate decimals:
- Default: 1 decimal place (e.g., "0.5%")
- Can be configured: `formatPercentage(value, 2)` → "0.01%"

## Files Updated

All progress bars in these files now use the new helper:
- `app/dashboard/countries/[country]/page.tsx` (3 progress bars)
- `app/dashboard/regions/[id]/page.tsx` (1 progress bar)
- `components/ipam/country-card.tsx` (1 progress bar)
- `components/ipam/region-card.tsx` (1 progress bar)

## Testing Scenarios

1. **Empty allocation (0%)**: Bar should be completely empty
2. **Tiny allocation (0.01%)**: Bar should show a small colored segment with "0.01%" text
3. **Small allocation (0.5%)**: Bar should show a small colored segment with "0.5%" text
4. **Normal allocation (50%)**: Bar should show half-filled
5. **Full allocation (100%)**: Bar should be completely filled
6. **Invalid values (NaN, null)**: Should default to 0% with empty bar
