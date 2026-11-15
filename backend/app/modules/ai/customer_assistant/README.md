# Customer Assistant

The Customer Assistant is a read-only, Customer-scoped harness. It retrieves only approved `customer_rag` chunks, combines them with typed menu/order read tools, and records a bounded conversation for the authenticated customer. Anonymous requests receive public content only. Prompt Guard is Customer-input-only and fail-open on classifier outage; no mutation tools are exposed.
