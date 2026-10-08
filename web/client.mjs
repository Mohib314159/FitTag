export const labels = {waist_flat:'Waist · flat',hip_flat:'Hip · flat',inseam:'Inseam',thigh:'Thigh',leg_opening:'Leg opening',length:'Length',pit_to_pit:'Chest · flat',hem_width:'Hem · flat',shoulder_width:'Shoulders',sleeve_length:'Sleeve'};
export function formatValue(cm, unit) { return (cm / (unit === 'in' ? 2.54 : 1)).toFixed(1); }
export function validateFile(file) {
  if (!file) return 'Choose a photo first.';
  if (file.size > 12 * 1024 * 1024) return 'Choose a photo smaller than 12 MB.';
  if (!['image/jpeg','image/png','image/webp'].includes(file.type)) return 'Choose a JPEG, PNG or WebP image. Export HEIC photos as JPEG first.';
  return '';
}
export function comparisonText(row, target) {
  if (!row || !Number.isFinite(target) || target < 10 || target > 100) return 'Enter a flat waist between 10 and 100 cm.';
  const diff = row.value_cm - target;
  if (Math.abs(diff) <= row.tolerance_cm) return 'The difference is within this estimate’s uncertainty. A fit verdict would be unreliable.';
  return `${Math.abs(diff).toFixed(1)} cm ${diff > 0 ? 'wider' : 'narrower'} laid flat (±${row.tolerance_cm.toFixed(1)} cm). This is a garment comparison, not a guaranteed fit.`;
}
