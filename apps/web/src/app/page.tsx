import { redirect } from "next/navigation";

// The app entry simply routes into the product; the proxy decides auth from there.
export default function Home() {
  redirect("/dashboard");
}
