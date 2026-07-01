# Code Review Checklist

A comprehensive checklist for reviewing code changes.

## 🎯 Purpose & Scope

- [ ] Does the change have a clear purpose?
- [ ] Is the scope appropriate (not too large, not too small)?
- [ ] Are there any unrelated changes that should be separate?

## ✅ Correctness

### Logic
- [ ] Does the code do what it claims?
- [ ] Are all edge cases handled?
- [ ] Are there off-by-one errors?
- [ ] Are loops correct (start, end, increment)?
- [ ] Are conditions correct (== vs ===, and vs or)?

### Error Handling
- [ ] Are exceptions caught appropriately?
- [ ] Are error messages helpful?
- [ ] Are resources cleaned up on error?
- [ ] Is there proper input validation?

### Data Integrity
- [ ] Are data transformations correct?
- [ ] Is data validation sufficient?
- [ ] Are there race conditions?
- [ ] Is concurrent access handled?

## 📖 Readability

### Naming
- [ ] Are names descriptive and unambiguous?
- [ ] Is naming consistent with the codebase?
- [ ] Are magic numbers replaced with named constants?
- [ ] Are boolean names clear (is_, has_, can_)?

### Structure
- [ ] Is the code well-organized?
- [ ] Are functions/methods focused and small?
- [ ] Is there deep nesting that could be simplified?
- [ ] Is the control flow clear?

### Documentation
- [ ] Are complex parts commented?
- [ ] Are public APIs documented?
- [ ] Is the documentation accurate?
- [ ] Are there outdated comments?

## 🏗️ Design

### Principles
- [ ] Does it follow SOLID principles?
- [ ] Is there code duplication (DRY)?
- [ ] Is the code testable?
- [ ] Are dependencies minimized?

### Patterns
- [ ] Are design patterns used appropriately?
- [ ] Are there anti-patterns?
- [ ] Is abstraction appropriate (not over/under)?

### Architecture
- [ ] Does it fit the existing architecture?
- [ ] Are boundaries respected?
- [ ] Is coupling appropriate?

## ⚡ Performance

### Efficiency
- [ ] Are expensive operations in loops?
- [ ] Are there N+1 queries?
- [ ] Is memory used efficiently?
- [ ] Are there unnecessary allocations?

### Scalability
- [ ] Will this scale with data growth?
- [ ] Are there potential bottlenecks?
- [ ] Is caching appropriate?

## 🔒 Security

### Input Handling
- [ ] Is user input validated?
- [ ] Is input sanitized for the context?
- [ ] Are there injection risks (SQL, XSS, etc.)?

### Access Control
- [ ] Are permissions checked?
- [ ] Is authentication sufficient?
- [ ] Are sensitive operations logged?

### Data Protection
- [ ] Are secrets handled securely?
- [ ] Is sensitive data encrypted?
- [ ] Is PII handled properly?

## 🧪 Testing

### Coverage
- [ ] Are there tests for new code?
- [ ] Do tests cover edge cases?
- [ ] Are integration tests needed?

### Quality
- [ ] Are tests clear and maintainable?
- [ ] Do tests actually verify behavior?
- [ ] Are tests independent?

## 🔄 Maintainability

### Dependencies
- [ ] Are dependencies appropriate?
- [ ] Are there unnecessary dependencies?
- [ ] Is version pinning correct?

### Future-Proofing
- [ ] Will this be easy to modify?
- [ ] Is it backwards compatible?
- [ ] Are there TODOs that need resolution?

---

## Quick Severity Guide

| Severity | Description | Examples |
|----------|-------------|----------|
| 🔴 Blocker | Must fix before merge | Security issues, data loss, crashes |
| 🟡 Important | Should fix soon | Performance, maintainability, missing tests |
| 🟢 Suggestion | Nice to have | Style, minor refactoring, documentation |
