# Vendor boundaries

Vendor-specific Skills describe how to operate or translate another product's
configuration. They do not replace a runtime integration.

- A model endpoint exposed by llama.cpp, vLLM, or a compatible service belongs
  under Quenda `providers` and selects a registered API protocol.
- Codex and Claude Code are agent products, not model providers. Do not put them
  in `providers` merely because they can call models.
- Invoking an external agent product requires a subprocess, SDK, or protocol
  backend with explicit lifecycle, workspace, permission, cancellation, and
  result contracts. Add that backend in code; add a vendor Skill only to teach
  configuration and operating workflow around the implemented backend.
- Keep one Quenda-native authoring Skill as the common workflow. Split a vendor
  into its own `skills/vendors/<vendor>/SKILL.md` package when it has enough
  distinct commands, schemas, or compatibility rules to justify independent
  activation.

This separation keeps vendor facts replaceable and prevents static Skill text
from pretending an integration exists when the runtime cannot execute it.
