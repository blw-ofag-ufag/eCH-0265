# Contributing

To ensure a smooth collaboration and maintain code quality, please adhere to the following workflow.

## Collaboration via GitHub

### Open an issue

Before writing any code, **open a GitHub Issue** to discuss the proposed change.
Whether it is a bug fix, feature request, or architectural adjustment, establish the scope in an issue first.

### Create a branch

Create a new branch for your specific task. Let GitHub autogenerate the branch name based on an issue; that way it's clear what you're trying to do on said branch.

### Submit a pull request

Once your work is ready:

1. Open a draft PR against the `main` branch.
2. Summarize your changes clearly in the description.
3. Link the PR to the issue it resolves (e.g. `Closes #42`).
4. Ensure there are no merge conflicts and all tests are passed before you change the status to a standard pull request.

### Merging and Deployment

Once your pull request is reviewed and approved, it can be merged into the `main` branch.

> [!IMPORTANT]
> Merging to `main` triggers an automatic deployment workflow. The new version of the RDF graph will be published to LINDAS, replacing the previous version. Ensure your changes are final and have passed all tests before merging.

## Naming conventions

### File naming convention

All files in this project should be named with `snake_case` and lowercase letters.

### RDF namespace naming convention

Namespaces follow a standardized pattern and include the project's eCH identifier, and the major version number[^1]:

[^1]: Embedding only the major version number in the namespace creates a structural contract. If a subsequent release introduces breaking changes, a new major version (and consequently, a new namespace) will be created. This isolates the versions, ensuring that existing data graphs can remain perfectly valid using the old schema while allowing downstream consumers to migrate to the new version at their own pace.

```
https://agriculture.ld.admin.ch/{identifier}/{version}/
```

Note that we use LINDAS namespaces in order to be able to dereference any defined resource.
Following this logic, we would assign a property `eppoCode` specified in a hypothetical version 3.4.1 of a standard eCH-1234 the following URI: 

```
https://agriculture.ld.admin.ch/eCH-1234/3/eppoCode
```

### RDF resource naming convention

Aligning with standard Semantic Web conventions, we enforce the following casing rules for URI local names:

- **Classes and individuals** (e.g., instances of `owl:Class` and instances of these): Use **PascalCase** (a.k.a. UpperCamelCase).
- **Properties** (e.g., `owl:ObjectProperty`, `owl:DatatypeProperty`): Use **camelCase** (a.k.a. lowerCamelCase). Don't include starting verbs, i.e. `eppoCode` would be preferred over `hasEppoCode`.

Ensure identifiers are meaningful to facilitate readability and improve [DX](https://en.wikipedia.org/wiki/Developer_experience).

For individuals, use a sub-namespace based on the most important classes. For example, if the project namespace is `https://agriculture.ld.admin.ch/eCH-1234/2/`, use `https://agriculture.ld.admin.ch/eCH-1234/2/person/` for all people:

``` ttl
@prefix eCH-1234: <https://agriculture.ld.admin.ch/eCH-1234/2/> .
@prefix person:   <https://agriculture.ld.admin.ch/eCH-1234/2/person/> .

person:1 a eCH-1234:Person .
person:2 a eCH-1234:Person .
person:3 a eCH-1234:Person .
```

## Alignment with eCH processes

To maintain consistency, the releases of this repository must strictly align with the official status of the corresponding document on [ech.ch](https://www.ech.ch/).

- **Official releases:** A GitHub release is *only* created when the document is officially published as an approved standard on the eCH website.
- **Pre-releases (QS/ÖK):** While the project is in intermediate stages such as quality control (QS) or public consultation (ÖK), we use pre-releases.

For a comprehensive overview of the standardization phases, please refer to the [eCH-0003 guidelines](https://www.ech.ch/de/ech/ech-0003).

## Contact

Do you have questions? Please do not hesitate to contact us at [agridata.ch@blw.admin.ch](mailto:agridata.ch@blw.admin.ch), open an [issue in this repository](../../issues), or directly submit a [Request for Change (RFC) via the official eCH feedback form](https://ech.ch/de/ech-standards/standardisierungsprozess/request-change-rfc).
