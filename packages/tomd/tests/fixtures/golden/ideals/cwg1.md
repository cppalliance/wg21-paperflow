*This is an unofficial snapshot of the ISO/IEC JTC1 SC22 WG21 Core Issues List revision 120a. See http://www.open-std.org/jtc1/sc22/wg21/ for the official list.*

2026-05-31

---

## What if two using-declarations refer to the same function but the declarations introduce different default-arguments?

Section: 9.3.4.7  [dcl.fct.default](https://wg21.link/dcl.fct.default)

Status: TC1

Submitter: Bill Gibbons

Date: unknown

6.4 [[basic.scope](https://wg21.link/basic.scope#4)] paragraph 4 says:

Given a set of declarations in a single declarative region, each of which specifies the same unqualified name
- they shall all refer to the same entity, or all refer to functions ...

9.3.4.7 [dcl.fct.default](https://wg21.link/dcl.fct.default#9) paragraph 9 says:

When a declaration of a function is introduced by way of a using-declaration  (9.10 [namespace.udecl](https://wg21.link/namespace.udecl)), any default argument information associated with the declaration is imported as well.

This is not really clear regarding what happens in the following case:

```
namespace A {
  extern "C" void f(int = 5);
}
namespace B {
  extern "C" void f(int = 7);
}

using A::f;
using B::f;

f(); // ???
```

Proposed resolution (10/00):

Add the following at the end of 12.2.4 [[over.match.best](https://wg21.link/over.match.best)]:

If the best viable function resolves to a function for which multiple declarations were found, and if at least two of these
declarations — or the declarations they refer to in the case of using-declaration s — specify a default argument that made the function viable, the program is ill-formed.

[Example:

```
namespace A {
  extern "C" void f(int = 5);
}

namespace B {
  extern "C" void f(int = 5);
}

using A::f; using B::f;

void use() { f(3); // OK, default argument was not used for viability f(); // Error: found default argument twice }
```

—*end example*]
