// BUG: discount is added instead of subtracted
export function finalPrice(price: number, discount: number): number {
  return price + discount;
}
