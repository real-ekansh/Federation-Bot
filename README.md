# **HyperFedBot is a Telegram Bot for the Federation Owner's to Manage there Appeals.**
 
 ## **What the Bot Does?**

### **Users can submit two types of appeals:**


1. **Fed Unban Appeal:** Request to be unbanned from the federation.

2. **Fed Admin Request:** Request to become a federation admin.


### **When a user sends /appeal, the bot shows an inline keyboard with two options:**

🔓 Fed Unban Appeal

👑 Fed Admin Request

**When the user selects one, the bot saves the appeal in a SQLite database with status pending and notifies the admin.**

The admin (identified by ADMIN_ID) can:

View all pending appeals using /pending.

Approve or reject appeals using /approve <appeal_id> or /reject <appeal_id>.

When resolved, the bot notifies the user of the appeal status.

## **Summary:**
Feature Who Uses It Purpose
Fed Unban Appeal Any user Request to be unbanned from the federation
Fed Admin Request Any user Request to become a federation admin
Appeal management (approve/reject) Federation admin Approve or reject user appeals
So, the bot is designed for both:
Submitting federation unban appeals, and

Requesting federation admin status.

It is not limited to only one of these functions but supports both via the appeal system.
