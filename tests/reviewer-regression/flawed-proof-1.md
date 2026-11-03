# Flawed proof 1

**Claim:** For all n >= 1, 1 + 2 + ... + n = n(n+1)/2 + 1.

**Proof:** Assume it holds for n = k: 1 + ... + k = k(k+1)/2 + 1. Then 1 + ... + (k+1) = k(k+1)/2 + 1 + (k+1) = (k+1)(k+2)/2 + 1. So it holds for all n by induction.

(The inductive step is fine. There is no base case, and the claim is false: n = 1 gives 1 = 2.)
