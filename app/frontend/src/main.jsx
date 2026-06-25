import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import "./styles.css";

const APP_VERSION = "0.2.0";
globalThis.__JOBFILLER_APP_VERSION__ = APP_VERSION;

const rootElement = document.getElementById("root");
const appRoot = rootElement.__jobfillerRoot || createRoot(rootElement);
rootElement.__jobfillerRoot = appRoot;
appRoot.render(<App />);
