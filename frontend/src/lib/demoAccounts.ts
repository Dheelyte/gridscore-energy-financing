/** Well-known synthetic demo logins, mirrored from scripts/seed_demo.py. Shown on
 *  the login screen so hackathon judges can jump into any role in one click.
 *  These only exist in the seeded demo database — never in production. */

export const DEMO_PASSWORD = "GridScore!Demo1";

export interface DemoAccount {
  email: string;
  password: string;
  role: string;
  /** Short role label for the button. */
  label: string;
  /** One line on what this role gets to see. */
  blurb: string;
  /** Where to land after signing in. */
  landing: string;
}

export const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    email: "analyst@gridscore.ai",
    password: DEMO_PASSWORD,
    role: "operator_analyst",
    label: "Operator analyst",
    blurb: "Score customers & see the reject → approve flip",
    landing: "/console",
  },
  {
    email: "lender@gridscore.ai",
    password: DEMO_PASSWORD,
    role: "lender_viewer",
    label: "Lender / DFI",
    blurb: "Portfolio analytics & the network-effect chart",
    landing: "/lender",
  },
  {
    email: "admin@gridscore.ai",
    password: DEMO_PASSWORD,
    role: "platform_admin",
    label: "Platform admin",
    blurb: "Operators, users & the immutable audit log",
    landing: "/admin",
  },
];
