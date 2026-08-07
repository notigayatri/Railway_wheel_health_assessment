# Digital Wheel Lifecycle Module

This module is responsible for managing wheel assets, inspection history,
health records, and lifecycle information.

It supports two operating modes:

1. Demo Mode
   - Automatically generates Asset IDs.
   - Used with public datasets that do not contain wheel metadata.

2. Deployment Mode
   - Uses inspector-entered metadata such as Train ID, Coach ID,
     Axle Number and Wheel Position.

Future components:
- Health Index
- Reliability History
- Maintenance History
- Inspection Timeline