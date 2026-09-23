function getDiscount(total, isMember) {
  let discount = 0;
  if (total > 100) {
    discount = 10;
  }
  if (isMember) {
    discount += 5;
  }
  return discount;
}
