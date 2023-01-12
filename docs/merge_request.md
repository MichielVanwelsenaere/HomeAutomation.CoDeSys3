## Merge request (pull request)

## **GIT side**

1. Create own fork (if you not already did)
2. Don't change the default `.ecp` for your own config
3. Optional: Create branch
4. Code 
4. Prepare for export, see below. Add documentation
5. Create merge/pull request from your repo to this.


## **Prepare for export**

1. Save file the `.ecp`
    - Make sure the original ecp is **unmodified**
    - Save with another name.

2. Run export (from your modified ecp)
    - Export all files except the `automation`
    - You can export Variables/Library if you see fit
      - Codesys v3 >>> [Exports\PLCopen.xml](/src/Exports/PLCopen.xml)
      - PLCopen XML >>> [Exports\CodesysV3.export](/src/Exports/CodesysV3.export)

3. Open the original `.ecp`, here we need to upgrade the basic version for newcomers. So keep your config out.
    - Follow [this guide](/docs/FAQ/Howto_updating_function_blocks.md) to update your blocks