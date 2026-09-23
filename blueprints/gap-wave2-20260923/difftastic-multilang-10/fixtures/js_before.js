function getDiscount(total, isMember) {
  let discount = 0;
  if (total > 100) {
    discount = 10;
  }
  return discount;
}
