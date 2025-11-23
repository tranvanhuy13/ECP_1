import React from "react";
import { Alert } from "react-bootstrap";

function Message({ variant, children }) {
  return <Alert variant={variant}>{children}</Alert>;
}
//message default props
export default Message;
