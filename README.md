# eCH-0265: Agrardaten -- Flächen und Kulturen

This is the repository for technical artefacts related to this specification.
Primarily, this repo contains:

* XSDs
* UML diagrams

The main branch contains the work in progress. Proposals are in version or feature branches. Published versions are in Releases. Released versions are published additionally on eCH and on BLW/OFAG/UFAG websites.

# Repository management policy
This section explains how this repository is governed.

## Membership and roles management

- All members of the Expert group outside of the FOAG receive the **“Outside collaborator”** organization membership. They have the “Read” role for all the eCH repositories.
Additionally, they may:

  - Waive this role for selected eCH repos where they are not directly involved (not part of the Expert group) and do not plan to get involved with.

  - Waive this role completely if they do not plan to contribute on GitHub at all and consider this pure spam.

  - Ask for the **Write** role in the repo(s) associated with their own Arbeitsgruppe(n) if they plan to contribute directly with Pull Requests (PR).

- Regular external developers are integrated into the organization as **“Outside Collaborator”** and receive by default the **Write** role on all eCH repositories.

Membership and roles are managed by the CCDT members.
Memberships and roles can be given or removed as soon as needed. CCDT makes a regular check of active users and adapts the accesses as needed.

## Issue management

Issues MUST be opened using the available template (see picture). This ensures smooth coordination with the internal FOAG task board.

![image](https://github.com/user-attachments/assets/e4a44cc8-0b9b-4e12-a9ea-f4c865a35f98)

Issues need a meaningful title and a description clearly stating what the problem is or what needs to be changed/fixed.

Issues are triaged by the CCDT team, who also priotizes them and selects an assignee. They still remain a way for an open and honest discussion so everyone is invited to participate. The use of people mentions using“@username” is encouraged where an opinion is demanded.

Issues are only closed by a member of the CCDT team (either in the issue itself or via the merge of a linked PR) or by the author of the issue itself.

CCDT performs a review and triage of the issues, potentially closing stale ones, at least twice a year.

## Labels

The CCDT members manage the available labels for the issues in the eCH repositories.

The CCDT team is also responsible for issue labeling.

Each issue MUST have the following 2 labels:

- The ```JIRA``` label in order to ensure coordination with the FOAG internal task board

- One of ```PATCH```, ```MINOR``` or ```MAJOR```  in order to identify the change scope

All issues MAY have

- A label identifying the type of change request (```DOCUMENTATION```, ```ENHANCEMENT``` or ```BUG```)

- A label identifying the target release for issue resolution (e.g. ```1.3.0```)

- Additional labels, for example showcasing the urgency of the issue.

This labeling schema MAY be applied to Pull Requests (PR) too.

## Branch and release management

### Versioning

Version numbering follows the [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) guidelines with the following adaptations:

- Version numbering only considers Major, Minor, Patch and Pre-releases.

- A Patch can be, for example, typo fixes in the medatada or in the descriptions, which should not trigger an eCH review process.

- Pre-releases versions **MUST** be denoted by appending a hyphen (“-”) followed by an integer to the target main release number. E.g. **1.5.0-2** is the second pre-release for the 1.5.0 version.

### Branching

All of the eCH repositories adhere to the following general branch organization:

- A **“main”** branch, acting as the master
  - The **“main”** branch is to be considered productive, valid and binding within the eCH context. **For this reason, there is no merge into the main branch if not related to an official new release.**
  - The only exception of that is the README.md content, which is not considered part of the eCH standard and can thus be merged outside of the standard management cycle. Changes to the README.md MAY be committed directly into the main branch by the GRKDT team.


- **Release branches** named after the release version and prefixed with “Release-”(e.g. “Release-1.3.0”)
  - Release branches coalesce all the changes needed for the future release of the new version.
  - Release branches are opened by the CCDT team only.
  - Release branches MAY be published on GitHub as pre-releases (see “Review and publishing process“ below).


- **Development branches** named with a “Dev-” prefix followed by free text (e.g. “Dev-AFoletti_patch1_n”)
  - The Development branches fix specific issues or implement specific enhancements and are usually linked to an Issue.

### Review and publishing process

The review and publishing process of the code in this repository has 4 main steps.

1. Work is done in a Development branch. Once finished, the author opens a Pull Request (PR). Pull requests from **Development** branches into **Release** branches can be opened by every member with Write permissions.

![image](https://github.com/user-attachments/assets/75367751-ebfd-4f23-b050-f0f6772cc4f0)


2. Team CCDT reviews the PR and merges the code into the appropriate Release branch. **Only the CCDT Team can merge those PRs.**

3. Once a release is considered complete, the CCDT Team MUST publish a pre-release from this branch. **Exception** to that is a patch version, which does not need an eCH review process. A patch release can thus be merged into main and published as a new version by the CCDT alone.

    Pre-releases are tagged according to the versioning rules (see above) and given a meaningful name.
    ![image](https://github.com/user-attachments/assets/8c030ce4-983a-4806-9942-62aa4873cb66)

    They MUST be set as pre-release before publishing

    ![image](https://github.com/user-attachments/assets/49caace2-2d72-4351-9330-644dcc85c542)

    The pre-release then follow the eCH validation process according to the change scope (minor, major). The code and documentation of the pre-release is sent to the relevant stakeholders that have the opportunity to ask for modifications or accept the new release. 
    See [eCH-0003 - Leitfaden zur Genehmigung von Anträgen](https://ech.ch/de/ech/ech-0003) and [eCH-0150 - Change und Release Management von eCH-Standards](https://ech.ch/de/ech/ech-0150).

4. Once the eCH validation process is done and the release is accepted, the CCDT merges the release branch into main.

    ![image](https://github.com/user-attachments/assets/3f5f0ead-a3a9-42bf-96cd-52b1872df2f9)

5. The CCDT then publishes a new official release tagged with the appropriate release number.

![image](https://github.com/user-attachments/assets/5a0e1a7f-f1fa-4bd6-850f-cf66707f0af3)

## Contact

For general questions and request write access to this repo, please send a mail to kompetenzzentrumdigitaletransformation@blw.admin.ch
