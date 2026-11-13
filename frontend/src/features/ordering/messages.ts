import { formatPaise } from "@/shared/utils/format";

// Customer wording for the backend's stable refusal and blocker codes (DDR-110).
const TEXT: Record<string, string> = {
  cart_empty: "Your cart is empty.",
  dish_unavailable: "A dish in your cart is no longer available. Remove it to continue.",
  price_changed: "A price has changed since you added the dish. Review and accept the new price to continue.",
  address_required: "Choose a delivery address.",
  address_unknown: "Choose one of your saved delivery addresses.",
  not_serviceable: "This address is outside our delivery area.",
  below_minimum: "Add more dishes: the minimum order is a food subtotal of ₹500.",
  cart_mixed: "TEST dishes and regular dishes cannot be ordered together.",
  coupon_unknown: "This coupon code is not valid.",
  coupon_inactive: "This coupon is not active.",
  coupon_not_started: "This coupon is not valid yet.",
  coupon_expired: "This coupon has expired.",
  coupon_used_up: "This coupon has reached its usage limit.",
  coupon_minimum: "The food subtotal is below this coupon's minimum.",
  coupon_not_for_order: "This coupon cannot be used with these dishes.",
};

export function describe(code: string, fallback = "Something went wrong. Try again."): string {
  return TEXT[code] ?? fallback;
}

export function minimumGap(subtotal: number, minimum: number): string | null {
  return subtotal >= minimum
    ? null
    : `Add ${formatPaise(minimum - subtotal)} more to reach the ₹500 minimum.`;
}
