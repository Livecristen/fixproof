function sum(xs) {
  let t = 0;
  for (let i = 0; i < xs.length; i++) t += xs[i];
  return t;
}
module.exports = { sum };
