// BUG: off-by-one, skips the last element
function sum(xs) {
  let t = 0;
  for (let i = 0; i < xs.length - 1; i++) t += xs[i];
  return t;
}
module.exports = { sum };
