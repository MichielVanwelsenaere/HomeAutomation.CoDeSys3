## How to contribute

#### **Did you find a bug?**

* **Ensure the bug was not already reported** by searching on GitHub under [Issues](https://github.com/MichielVanwelsenaere/HomeAutomation.CoDeSys3/issues).

* If you're unable to find an open issue addressing the problem, [open a new one](https://github.com/MichielVanwelsenaere/HomeAutomation.CoDeSys3/issues/new). Be sure to include a **title and clear description**, as much relevant information as possible, and a **code sample** or a **clear explanation** demonstrating the expected behavior that is not occurring.


#### **Did you write a patch that fixes a bug?**

* Make sure there is a Github issue for the patch you are writing.

* Open a new GitHub pull request with the patch.

* Ensure the PR description clearly describes the problem and solution. Include the relevant issue number.

In case your specific project differs to much from the reference project in this repository, use the PLCopen XML to export the specific artifacts including the fix and paste them in the relevant Github issue.

#### **Do you intend to add a new feature or change an existing one?**

* Suggest your change/feature in the [Gitter chat](https://gitter.im/MichielVanwelsenaere/HomeAutomation.CoDeSys3) and start writing code.

* Do not open an issue on GitHub until you have collected positive feedback about the change. GitHub issues are primarily intended for bug reports, fixes and milestone tracking.

#### **Do you have questions about the source code?**

* Ask any question about how to use the source code in the [Gitter chat](https://gitter.im/MichielVanwelsenaere/HomeAutomation.CoDeSys3).

# Merge request (pull request)

## **GIT side**

1. Create own fork (if you not already did)
2. Don't change the default `.ecp` for your own config
3. Optional: Create branch 
4. Code
5. Prepare for export, see below. 
6. Add documentation in the markdown files.
6. Create merge/pull request from your repo to this.

## **Prepare for export**

An export contains `.export` and `.xml` for people to update. The `.ecp` is upgraded to the new changes, so its a basic version for newcomers.

1. Save file the `.ecp`

   - Make sure the original ecp is **unmodified**
   - Save with another name.

2. Run export (from your modified ecp)

   - Export all files except configs
   
     <img src="_img/GettingStartedGuide/Export_all_except_POU.png" height="400">
     
     So no `*variables`, `PRG's` and `PersistenceVars`
   - You can export Variables/Library if you see fit
     - Codesys v3 >>> [Exports\PLCopen.xml](../src/Exports/PLCopen.xml)
     - PLCopen XML >>> [Exports\CodesysV3.export](../src/Exports/CodesysV3.export)

3. Open the original `.ecp`. Keep your config out.
    - Follow [this guide](FAQ/Howto_updating_function_blocks.md) to update your blocks

    - Add 1 example of the new function block/methods to the POU
    - Document the new function block/methods in the POU![](img/clip20230118225246.png)